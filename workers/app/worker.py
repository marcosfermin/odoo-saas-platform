#!/usr/bin/env python3
"""
Background Job Worker Service
Handles asynchronous tasks using Redis Queue (RQ)
"""

import os
import sys
import time
import logging
import signal
from datetime import datetime, timedelta
import redis
from rq import Worker, Queue, Connection
from rq.job import Job

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from workers.jobs.tenant_jobs import (
    provision_tenant_job,
    delete_tenant_job,
    install_module_job,
    uninstall_module_job,
    backup_tenant_job,
    restore_tenant_job
)

from workers.jobs.backup_jobs import (
    backup_database_to_s3_job,
    restore_database_from_s3_job,
    cleanup_old_backups_job,
    verify_backup_integrity_job
)

from workers.jobs.billing_jobs import (
    process_payment_webhook_job,
    send_invoice_job,
    process_subscription_change_job,
    send_billing_notification_job
)

from workers.jobs.notification_jobs import (
    send_email_job,
    send_sms_job,
    send_slack_notification_job,
    send_welcome_email_job,
    send_support_notification_job
)

from workers.jobs.monitoring_jobs import (
    collect_tenant_metrics_job,
    check_system_health_job,
    cleanup_old_logs_job,
    generate_usage_report_job
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
REDIS_DB = int(os.environ.get('REDIS_WORKER_DB', '3'))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)

WORKER_NAME = os.environ.get('WORKER_NAME', f'worker-{os.getpid()}')
WORKER_QUEUES = os.environ.get('WORKER_QUEUES', 'high,default,low').split(',')

# Queue priorities
HIGH_PRIORITY_QUEUE = 'high'
DEFAULT_QUEUE = 'default'
LOW_PRIORITY_QUEUE = 'low'

class WorkerManager:
    """Manages RQ workers and job queues"""
    
    def __init__(self):
        self.redis_conn = self.get_redis_connection()
        self.queues = self.initialize_queues()
        self.worker = None
        self.running = False
        
    def get_redis_connection(self):
        """Get Redis connection"""
        try:
            conn = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True
            )
            conn.ping()
            logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def initialize_queues(self):
        """Initialize job queues"""
        queues = []
        for queue_name in WORKER_QUEUES:
            queue = Queue(queue_name, connection=self.redis_conn)
            queues.append(queue)
            logger.info(f"Initialized queue: {queue_name}")
        
        return queues
    
    def create_worker(self):
        """Create RQ worker"""
        self.worker = Worker(
            self.queues,
            connection=self.redis_conn,
            name=WORKER_NAME
        )
        
        # Set worker properties
        self.worker.job_timeout = 1800  # 30 minutes default timeout
        self.worker.result_ttl = 86400  # Keep results for 24 hours
        
        logger.info(f"Created worker: {WORKER_NAME}")
        return self.worker
    
    def start_worker(self):
        """Start the worker"""
        if not self.worker:
            self.create_worker()
        
        logger.info(f"Starting worker {WORKER_NAME} for queues: {WORKER_QUEUES}")
        
        self.running = True
        
        try:
            # Start worker with exception handling
            self.worker.work(
                with_scheduler=True,  # Enable job scheduling
                logging_level='INFO'
            )
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            self.stop_worker()
        except Exception as e:
            logger.error(f"Worker error: {e}")
            self.stop_worker()
            raise
    
    def stop_worker(self):
        """Stop the worker gracefully"""
        self.running = False
        
        if self.worker:
            logger.info("Stopping worker...")
            self.worker.request_stop()
    
    def setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.stop_worker()
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

def enqueue_job(queue_name, func, *args, job_timeout=1800, **kwargs):
    """
    Enqueue a job in the specified queue
    
    Args:
        queue_name (str): Queue name ('high', 'default', 'low')
        func: Function to execute
        *args: Function arguments
        job_timeout (int): Job timeout in seconds
        **kwargs: Function keyword arguments
    
    Returns:
        Job: RQ Job object
    """
    try:
        redis_conn = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD
        )
        
        queue = Queue(queue_name, connection=redis_conn)
        
        job = queue.enqueue(
            func,
            *args,
            job_timeout=job_timeout,
            **kwargs
        )
        
        logger.info(f"Enqueued job {job.id} in queue {queue_name}")
        return job
        
    except Exception as e:
        logger.error(f"Failed to enqueue job: {e}")
        raise

def enqueue_scheduled_job(queue_name, func, scheduled_time, *args, **kwargs):
    """
    Schedule a job to run at a specific time
    
    Args:
        queue_name (str): Queue name
        func: Function to execute
        scheduled_time (datetime): When to run the job
        *args: Function arguments
        **kwargs: Function keyword arguments
    
    Returns:
        Job: RQ Job object
    """
    try:
        redis_conn = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD
        )
        
        queue = Queue(queue_name, connection=redis_conn)
        
        job = queue.enqueue_at(
            scheduled_time,
            func,
            *args,
            **kwargs
        )
        
        logger.info(f"Scheduled job {job.id} in queue {queue_name} for {scheduled_time}")
        return job
        
    except Exception as e:
        logger.error(f"Failed to schedule job: {e}")
        raise

def get_job_status(job_id):
    """
    Get status of a job
    
    Args:
        job_id (str): Job ID
    
    Returns:
        dict: Job status information
    """
    try:
        redis_conn = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD
        )
        
        job = Job.fetch(job_id, connection=redis_conn)
        
        return {
            'id': job.id,
            'status': job.get_status(),
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'ended_at': job.ended_at.isoformat() if job.ended_at else None,
            'result': job.result,
            'exc_info': job.exc_info,
            'meta': job.meta
        }
        
    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        return None

def cancel_job(job_id):
    """
    Cancel a job
    
    Args:
        job_id (str): Job ID
    
    Returns:
        bool: True if cancelled successfully
    """
    try:
        redis_conn = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD
        )
        
        job = Job.fetch(job_id, connection=redis_conn)
        job.cancel()
        
        logger.info(f"Cancelled job {job_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to cancel job: {e}")
        return False

def get_queue_info():
    """
    Get information about all queues
    
    Returns:
        dict: Queue information
    """
    try:
        redis_conn = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD
        )
        
        queue_info = {}
        
        for queue_name in ['high', 'default', 'low']:
            queue = Queue(queue_name, connection=redis_conn)
            
            queue_info[queue_name] = {
                'length': len(queue),
                'jobs': [job.id for job in queue.jobs],
                'failed_jobs': len(queue.failed_job_registry),
                'started_jobs': len(queue.started_job_registry),
                'finished_jobs': len(queue.finished_job_registry)
            }
        
        return queue_info
        
    except Exception as e:
        logger.error(f"Failed to get queue info: {e}")
        return {}

def cleanup_old_jobs():
    """Clean up old completed and failed jobs"""
    try:
        redis_conn = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD
        )
        
        cutoff_time = datetime.utcnow() - timedelta(days=7)  # Keep jobs for 7 days
        
        for queue_name in ['high', 'default', 'low']:
            queue = Queue(queue_name, connection=redis_conn)
            
            # Clean up finished jobs
            finished_registry = queue.finished_job_registry
            job_ids = finished_registry.get_job_ids()
            
            for job_id in job_ids:
                try:
                    job = Job.fetch(job_id, connection=redis_conn)
                    if job.ended_at and job.ended_at < cutoff_time:
                        finished_registry.remove(job_id)
                        logger.info(f"Cleaned up finished job {job_id}")
                except:
                    # Job might not exist anymore
                    continue
            
            # Clean up failed jobs
            failed_registry = queue.failed_job_registry
            job_ids = failed_registry.get_job_ids()
            
            for job_id in job_ids:
                try:
                    job = Job.fetch(job_id, connection=redis_conn)
                    if job.ended_at and job.ended_at < cutoff_time:
                        failed_registry.remove(job_id)
                        logger.info(f"Cleaned up failed job {job_id}")
                except:
                    continue
        
        logger.info("Completed job cleanup")
        
    except Exception as e:
        logger.error(f"Failed to cleanup old jobs: {e}")

if __name__ == '__main__':
    # Create and start worker manager
    manager = WorkerManager()
    manager.setup_signal_handlers()
    
    logger.info("Starting background job worker...")
    manager.start_worker()