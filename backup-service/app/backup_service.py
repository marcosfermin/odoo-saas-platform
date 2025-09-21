#!/usr/bin/env python3
"""
S3 Backup Service with KMS Encryption
Handles automated backups of PostgreSQL databases and file storage
"""

import os
import sys
import boto3
import gzip
import logging
import hashlib
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
import tempfile
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.models import BackupRecord
from shared.database import get_db_session

logger = logging.getLogger(__name__)

class S3BackupService:
    """Handles S3 backup operations with KMS encryption"""
    
    def __init__(self):
        # AWS Configuration
        self.aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.environ.get('AWS_REGION', 'us-east-1')
        self.s3_bucket = os.environ.get('S3_BACKUP_BUCKET')
        self.kms_key_id = os.environ.get('KMS_KEY_ID')
        
        # Database Configuration
        self.db_host = os.environ.get('DB_HOST', 'localhost')
        self.db_port = os.environ.get('DB_PORT', '5432')
        self.db_user = os.environ.get('DB_USER', 'odoo')
        self.db_password = os.environ.get('DB_PASSWORD', 'odoo')
        
        # Backup Configuration
        self.backup_retention_days = int(os.environ.get('BACKUP_RETENTION_DAYS', '30'))
        self.compression_level = int(os.environ.get('BACKUP_COMPRESSION_LEVEL', '6'))
        
        # Initialize S3 client
        self.s3_client = self._init_s3_client()
        self.kms_client = self._init_kms_client()
        
    def _init_s3_client(self):
        """Initialize S3 client"""
        try:
            session = boto3.Session(
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.aws_region
            )
            
            s3_client = session.client('s3')
            
            # Test connection
            s3_client.head_bucket(Bucket=self.s3_bucket)
            
            logger.info(f"Connected to S3 bucket: {self.s3_bucket}")
            return s3_client
            
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
    def _init_kms_client(self):
        """Initialize KMS client"""
        try:
            session = boto3.Session(
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.aws_region
            )
            
            kms_client = session.client('kms')
            
            # Test KMS key access
            if self.kms_key_id:
                kms_client.describe_key(KeyId=self.kms_key_id)
                logger.info(f"Connected to KMS key: {self.kms_key_id}")
            
            return kms_client
            
        except Exception as e:
            logger.error(f"Failed to initialize KMS client: {e}")
            raise
    
    def create_database_backup(self, database_name: str, tenant_id: Optional[int] = None) -> Dict:
        """
        Create PostgreSQL database backup
        
        Args:
            database_name (str): Database name to backup
            tenant_id (int, optional): Tenant ID for organization
        
        Returns:
            dict: Backup result with S3 location and metadata
        """
        logger.info(f"Starting backup for database: {database_name}")
        
        try:
            # Generate backup filename
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"{database_name}_{timestamp}.sql"
            compressed_filename = f"{backup_filename}.gz"
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                backup_file = temp_path / backup_filename
                compressed_file = temp_path / compressed_filename
                
                # Create database dump
                self._create_database_dump(database_name, backup_file)
                
                # Compress the backup
                self._compress_file(backup_file, compressed_file)
                
                # Calculate file hash for integrity verification
                file_hash = self._calculate_file_hash(compressed_file)
                
                # Upload to S3 with KMS encryption
                s3_key = self._generate_s3_key(database_name, compressed_filename, tenant_id)
                upload_result = self._upload_to_s3(compressed_file, s3_key)
                
                # Create backup record in database
                backup_record = self._create_backup_record(
                    database_name=database_name,
                    tenant_id=tenant_id,
                    s3_key=s3_key,
                    file_size=compressed_file.stat().st_size,
                    file_hash=file_hash,
                    backup_type='database'
                )
                
                logger.info(f"Successfully created backup for {database_name}: {s3_key}")
                
                return {
                    'status': 'success',
                    'backup_id': backup_record.id,
                    'database_name': database_name,
                    'tenant_id': tenant_id,
                    's3_key': s3_key,
                    's3_url': f"s3://{self.s3_bucket}/{s3_key}",
                    'file_size': compressed_file.stat().st_size,
                    'file_hash': file_hash,
                    'created_at': backup_record.created_at.isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to create backup for {database_name}: {e}")
            raise
    
    def restore_database_backup(self, backup_id: int, target_database: str) -> Dict:
        """
        Restore database from S3 backup
        
        Args:
            backup_id (int): Backup record ID
            target_database (str): Target database name
        
        Returns:
            dict: Restore result
        """
        logger.info(f"Starting restore for backup ID: {backup_id}")
        
        try:
            # Get backup record
            with get_db_session() as session:
                backup_record = session.query(BackupRecord).get(backup_id)
                if not backup_record:
                    raise Exception(f"Backup record {backup_id} not found")
                
                if backup_record.backup_type != 'database':
                    raise Exception(f"Invalid backup type: {backup_record.backup_type}")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                compressed_file = temp_path / f"backup_{backup_id}.sql.gz"
                restored_file = temp_path / f"backup_{backup_id}.sql"
                
                # Download from S3
                self._download_from_s3(backup_record.s3_key, compressed_file)
                
                # Verify file integrity
                if not self._verify_file_integrity(compressed_file, backup_record.file_hash):
                    raise Exception("Backup file integrity verification failed")
                
                # Decompress the backup
                self._decompress_file(compressed_file, restored_file)
                
                # Restore database
                self._restore_database(target_database, restored_file)
                
                logger.info(f"Successfully restored backup {backup_id} to {target_database}")
                
                return {
                    'status': 'success',
                    'backup_id': backup_id,
                    'target_database': target_database,
                    'restored_at': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to restore backup {backup_id}: {e}")
            raise
    
    def backup_filestore(self, tenant_id: int, filestore_path: str) -> Dict:
        """
        Backup tenant filestore to S3
        
        Args:
            tenant_id (int): Tenant ID
            filestore_path (str): Path to filestore directory
        
        Returns:
            dict: Backup result
        """
        logger.info(f"Starting filestore backup for tenant {tenant_id}")
        
        try:
            if not Path(filestore_path).exists():
                raise Exception(f"Filestore path does not exist: {filestore_path}")
            
            # Generate backup filename
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            archive_filename = f"tenant_{tenant_id}_filestore_{timestamp}.tar.gz"
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                archive_file = temp_path / archive_filename
                
                # Create tar.gz archive of filestore
                self._create_filestore_archive(filestore_path, archive_file)
                
                # Calculate file hash
                file_hash = self._calculate_file_hash(archive_file)
                
                # Upload to S3
                s3_key = self._generate_s3_key(f"tenant_{tenant_id}", archive_filename, tenant_id)
                self._upload_to_s3(archive_file, s3_key)
                
                # Create backup record
                backup_record = self._create_backup_record(
                    database_name=None,
                    tenant_id=tenant_id,
                    s3_key=s3_key,
                    file_size=archive_file.stat().st_size,
                    file_hash=file_hash,
                    backup_type='filestore'
                )
                
                logger.info(f"Successfully backed up filestore for tenant {tenant_id}: {s3_key}")
                
                return {
                    'status': 'success',
                    'backup_id': backup_record.id,
                    'tenant_id': tenant_id,
                    's3_key': s3_key,
                    'file_size': archive_file.stat().st_size,
                    'file_hash': file_hash,
                    'created_at': backup_record.created_at.isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to backup filestore for tenant {tenant_id}: {e}")
            raise
    
    def cleanup_old_backups(self) -> Dict:
        """
        Clean up old backups based on retention policy
        
        Returns:
            dict: Cleanup result
        """
        logger.info("Starting backup cleanup")
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.backup_retention_days)
            
            with get_db_session() as session:
                # Get old backup records
                old_backups = session.query(BackupRecord).filter(
                    BackupRecord.created_at < cutoff_date,
                    BackupRecord.status == 'completed'
                ).all()
                
                deleted_count = 0
                total_size_freed = 0
                
                for backup in old_backups:
                    try:
                        # Delete from S3
                        self.s3_client.delete_object(
                            Bucket=self.s3_bucket,
                            Key=backup.s3_key
                        )
                        
                        # Update backup record status
                        backup.status = 'deleted'
                        backup.deleted_at = datetime.utcnow()
                        
                        total_size_freed += backup.file_size or 0
                        deleted_count += 1
                        
                        logger.info(f"Deleted old backup: {backup.s3_key}")
                        
                    except Exception as e:
                        logger.error(f"Failed to delete backup {backup.id}: {e}")
                
                session.commit()
                
                logger.info(f"Cleanup completed: {deleted_count} backups deleted, {total_size_freed / (1024*1024):.2f} MB freed")
                
                return {
                    'status': 'success',
                    'deleted_count': deleted_count,
                    'total_size_freed': total_size_freed,
                    'cutoff_date': cutoff_date.isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")
            raise
    
    def _create_database_dump(self, database_name: str, output_file: Path):
        """Create PostgreSQL database dump"""
        cmd = [
            'pg_dump',
            '-h', self.db_host,
            '-p', self.db_port,
            '-U', self.db_user,
            '-f', str(output_file),
            '--format=plain',
            '--no-owner',
            '--no-privileges',
            database_name
        ]
        
        env = os.environ.copy()
        env['PGPASSWORD'] = self.db_password
        
        process = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        if process.returncode != 0:
            raise Exception(f"pg_dump failed: {process.stderr}")
    
    def _restore_database(self, database_name: str, backup_file: Path):
        """Restore PostgreSQL database from dump"""
        # First, create the database if it doesn't exist
        create_db_cmd = [
            'createdb',
            '-h', self.db_host,
            '-p', self.db_port,
            '-U', self.db_user,
            database_name
        ]
        
        env = os.environ.copy()
        env['PGPASSWORD'] = self.db_password
        
        # Try to create database (ignore if exists)
        subprocess.run(create_db_cmd, env=env, capture_output=True)
        
        # Restore from backup
        restore_cmd = [
            'psql',
            '-h', self.db_host,
            '-p', self.db_port,
            '-U', self.db_user,
            '-d', database_name,
            '-f', str(backup_file)
        ]
        
        process = subprocess.run(
            restore_cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        if process.returncode != 0:
            raise Exception(f"Database restore failed: {process.stderr}")
    
    def _create_filestore_archive(self, source_path: str, output_file: Path):
        """Create tar.gz archive of filestore"""
        cmd = [
            'tar',
            '-czf',
            str(output_file),
            '-C', os.path.dirname(source_path),
            os.path.basename(source_path)
        ]
        
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        if process.returncode != 0:
            raise Exception(f"Archive creation failed: {process.stderr}")
    
    def _compress_file(self, input_file: Path, output_file: Path):
        """Compress file using gzip"""
        with open(input_file, 'rb') as f_in:
            with gzip.open(output_file, 'wb', compresslevel=self.compression_level) as f_out:
                f_out.writelines(f_in)
    
    def _decompress_file(self, input_file: Path, output_file: Path):
        """Decompress gzip file"""
        with gzip.open(input_file, 'rb') as f_in:
            with open(output_file, 'wb') as f_out:
                f_out.writelines(f_in)
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def _verify_file_integrity(self, file_path: Path, expected_hash: str) -> bool:
        """Verify file integrity using hash"""
        actual_hash = self._calculate_file_hash(file_path)
        return actual_hash == expected_hash
    
    def _generate_s3_key(self, database_name: str, filename: str, tenant_id: Optional[int] = None) -> str:
        """Generate S3 object key"""
        date_prefix = datetime.utcnow().strftime('%Y/%m/%d')
        
        if tenant_id:
            return f"backups/tenants/{tenant_id}/{date_prefix}/{filename}"
        else:
            return f"backups/{database_name}/{date_prefix}/{filename}"
    
    def _upload_to_s3(self, file_path: Path, s3_key: str) -> Dict:
        """Upload file to S3 with KMS encryption"""
        extra_args = {}
        
        if self.kms_key_id:
            extra_args['ServerSideEncryption'] = 'aws:kms'
            extra_args['SSEKMSKeyId'] = self.kms_key_id
        
        self.s3_client.upload_file(
            str(file_path),
            self.s3_bucket,
            s3_key,
            ExtraArgs=extra_args
        )
        
        return {
            'bucket': self.s3_bucket,
            'key': s3_key,
            'encrypted': bool(self.kms_key_id)
        }
    
    def _download_from_s3(self, s3_key: str, local_file: Path):
        """Download file from S3"""
        self.s3_client.download_file(
            self.s3_bucket,
            s3_key,
            str(local_file)
        )
    
    def _create_backup_record(self, database_name: Optional[str], tenant_id: Optional[int],
                            s3_key: str, file_size: int, file_hash: str, backup_type: str) -> BackupRecord:
        """Create backup record in database"""
        with get_db_session() as session:
            backup_record = BackupRecord(
                tenant_id=tenant_id,
                database_name=database_name,
                backup_type=backup_type,
                s3_bucket=self.s3_bucket,
                s3_key=s3_key,
                file_size=file_size,
                file_hash=file_hash,
                status='completed',
                created_at=datetime.utcnow()
            )
            
            session.add(backup_record)
            session.commit()
            session.refresh(backup_record)
            
            return backup_record

    def list_backups(self, tenant_id: Optional[int] = None, backup_type: Optional[str] = None) -> List[Dict]:
        """
        List available backups
        
        Args:
            tenant_id (int, optional): Filter by tenant ID
            backup_type (str, optional): Filter by backup type
        
        Returns:
            list: List of backup records
        """
        try:
            with get_db_session() as session:
                query = session.query(BackupRecord).filter(
                    BackupRecord.status == 'completed'
                )
                
                if tenant_id:
                    query = query.filter(BackupRecord.tenant_id == tenant_id)
                
                if backup_type:
                    query = query.filter(BackupRecord.backup_type == backup_type)
                
                backups = query.order_by(BackupRecord.created_at.desc()).all()
                
                return [{
                    'id': backup.id,
                    'tenant_id': backup.tenant_id,
                    'database_name': backup.database_name,
                    'backup_type': backup.backup_type,
                    's3_key': backup.s3_key,
                    'file_size': backup.file_size,
                    'file_hash': backup.file_hash,
                    'created_at': backup.created_at.isoformat(),
                    'status': backup.status
                } for backup in backups]
                
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            raise

if __name__ == '__main__':
    # Example usage
    backup_service = S3BackupService()
    
    # Create a database backup
    # result = backup_service.create_database_backup('tenant_123')
    # print(f"Backup created: {result}")
    
    # List backups
    backups = backup_service.list_backups()
    print(f"Found {len(backups)} backups")