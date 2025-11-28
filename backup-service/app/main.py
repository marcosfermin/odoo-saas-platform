#!/usr/bin/env python3
"""
Backup Service Main Entry Point
"""
import os
import sys
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/backup-service.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point for backup service"""
    logger.info("Starting Backup Service...")

    # Import backup service after logging is configured
    try:
        from backup_service import BackupService

        # Initialize service
        service = BackupService()

        # Run the service
        logger.info("Backup service initialized successfully")
        service.run()

    except Exception as e:
        logger.error(f"Failed to start backup service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
