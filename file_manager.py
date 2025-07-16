#!/usr/bin/env python3
"""
File Manager Module for Resin Printer Control Application
Handles all file operations, upload, delete, and file listing functionality
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename
import logging

logger = logging.getLogger(__name__)

class FileManager:
    """
    Handles all file management operations for the printer application
    """
    
    def __init__(self, usb_drive_mount, allowed_extensions=None):
        """
        Initialize file manager with mount point and allowed extensions
        
        Args:
            usb_drive_mount (Path): Path to USB drive mount point
            allowed_extensions (set): Set of allowed file extensions
        """
        self.usb_drive_mount = Path(usb_drive_mount)
        self.allowed_extensions = allowed_extensions or {
            '.ctb', '.cbddlp', '.pwmx', '.pwmo', '.pwms', '.pws', '.pw0', '.pwx'
        }
        
        # Ensure mount point exists
        self.usb_drive_mount.mkdir(exist_ok=True)
        
        logger.info(f"File manager initialized with mount point: {self.usb_drive_mount}")
    
    def is_allowed_file(self, filename):
        """
        Check if file has allowed extension
        
        Args:
            filename (str): Name of the file to check
            
        Returns:
            bool: True if file is allowed, False otherwise
        """
        return Path(filename).suffix.lower() in self.allowed_extensions
    
    def get_disk_usage(self):
        """
        Get disk usage for the USB drive mount point
        
        Returns:
            dict: Dictionary with total, used, and free space in bytes
        """
        try:
            total, used, free = shutil.disk_usage(str(self.usb_drive_mount))
            return {
                'total': total,
                'free': free,
                'used': used
            }
        except Exception as e:
            logger.error(f"Error getting disk usage for {self.usb_drive_mount}: {e}")
            return {}
    
    def get_file_list(self):
        """
        Get list of all allowed files from USB drive
        
        Returns:
            list: List of dictionaries containing file information
        """
        files = []
        
        if not self.usb_drive_mount.exists() or not self.usb_drive_mount.is_dir():
            logger.warning(f"USB drive mount point does not exist: {self.usb_drive_mount}")
            return files
        
        try:
            for file_path in self.usb_drive_mount.glob("*"):
                if file_path.is_file() and self.is_allowed_file(file_path.name):
                    try:
                        stat = file_path.stat()
                        files.append({
                            'name': file_path.name,
                            'size': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                            'path': str(file_path),
                            'extension': file_path.suffix.lower()
                        })
                    except Exception as e:
                        logger.warning(f"Error reading file info for {file_path.name}: {e}")
                        continue
                        
        except PermissionError:
            logger.warning("Cannot access USB drive mount point - permission denied")
        except Exception as e:
            logger.error(f"Error reading USB drive: {e}")
        
        # Sort by modification time (newest first)
        return sorted(files, key=lambda x: x['modified'], reverse=True)
    
    def file_exists(self, filename):
        """
        Check if file exists in USB drive
        
        Args:
            filename (str): Name of the file to check
            
        Returns:
            bool: True if file exists, False otherwise
        """
        file_path = self.usb_drive_mount / filename
        return file_path.exists() and file_path.is_file()
    
    def get_file_path(self, filename):
        """
        Get full path to file
        
        Args:
            filename (str): Name of the file
            
        Returns:
            Path: Full path to the file
        """
        return self.usb_drive_mount / filename
    
    def get_file_info(self, filename):
        """
        Get detailed information about a specific file
        
        Args:
            filename (str): Name of the file
            
        Returns:
            dict: File information or None if file doesn't exist
        """
        file_path = self.get_file_path(filename)
        
        if not file_path.exists():
            return None
            
        try:
            stat = file_path.stat()
            return {
                'name': file_path.name,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'path': str(file_path),
                'extension': file_path.suffix.lower(),
                'size_mb': round(stat.st_size / (1024 * 1024), 2)
            }
        except Exception as e:
            logger.error(f"Error getting file info for {filename}: {e}")
            return None
    
    def save_uploaded_file(self, uploaded_file):
        """
        Save an uploaded file to the USB drive
        
        Args:
            uploaded_file: Flask uploaded file object
            
        Returns:
            tuple: (success: bool, message: str, filename: str or None)
        """
        if not uploaded_file.filename:
            return False, "No filename provided", None
            
        if not self.is_allowed_file(uploaded_file.filename):
            return False, f"File type not allowed: {uploaded_file.filename}", None
        
        # Secure the filename
        filename = secure_filename(uploaded_file.filename)
        
        if not filename:
            return False, "Invalid filename", None
        
        try:
            # Check if USB drive is accessible
            if not self.usb_drive_mount.exists():
                return False, "USB drive not accessible", None
            
            file_path = self.usb_drive_mount / filename
            
            # Check for duplicate files
            if file_path.exists():
                # Create a unique filename
                base_name = file_path.stem
                extension = file_path.suffix
                counter = 1
                
                while file_path.exists():
                    new_name = f"{base_name}_{counter}{extension}"
                    file_path = self.usb_drive_mount / new_name
                    counter += 1
                
                filename = file_path.name
                logger.info(f"File renamed to avoid conflict: {filename}")
            
            # Save the file
            uploaded_file.save(str(file_path))
            
            # Verify file was saved correctly
            if file_path.exists() and file_path.stat().st_size > 0:
                logger.info(f"File saved successfully: {filename}")
                return True, f"File saved: {filename}", filename
            else:
                return False, "File save verification failed", None
                
        except Exception as e:
            logger.error(f"Error saving file {filename}: {e}")
            return False, f"Error saving file: {str(e)}", None
    
    def delete_file(self, filename):
        """
        Delete a file from the USB drive
        
        Args:
            filename (str): Name of the file to delete
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            file_path = self.get_file_path(filename)
            
            if not file_path.exists():
                return False, f"File not found: {filename}"
            
            # Additional safety check
            if not file_path.is_file():
                return False, f"Path is not a file: {filename}"
            
            # Delete the file
            file_path.unlink()
            
            # Verify deletion
            if file_path.exists():
                return False, f"File deletion verification failed: {filename}"
            
            logger.info(f"File deleted successfully: {filename}")
            return True, f"File deleted: {filename}"
            
        except PermissionError:
            logger.error(f"Permission denied deleting file: {filename}")
            return False, f"Permission denied: {filename}"
        except Exception as e:
            logger.error(f"Error deleting file {filename}: {e}")
            return False, f"Error deleting file: {str(e)}"
    
    def cleanup_old_files(self, max_files=50, max_age_days=30):
        """
        Clean up old files to prevent storage issues
        
        Args:
            max_files (int): Maximum number of files to keep
            max_age_days (int): Maximum age of files in days
            
        Returns:
            tuple: (files_deleted: int, message: str)
        """
        try:
            files = self.get_file_list()
            deleted_count = 0
            current_time = datetime.now()
            
            # Sort by modification time (oldest first for deletion)
            files_by_age = sorted(files, key=lambda x: x['modified'])
            
            # Delete files older than max_age_days
            for file_info in files_by_age:
                file_modified = datetime.strptime(file_info['modified'], '%Y-%m-%d %H:%M:%S')
                age_days = (current_time - file_modified).days
                
                if age_days > max_age_days:
                    success, _ = self.delete_file(file_info['name'])
                    if success:
                        deleted_count += 1
                        logger.info(f"Deleted old file: {file_info['name']} (age: {age_days} days)")
            
            # If still too many files, delete oldest ones
            remaining_files = self.get_file_list()
            if len(remaining_files) > max_files:
                files_to_delete = len(remaining_files) - max_files
                oldest_files = sorted(remaining_files, key=lambda x: x['modified'])[:files_to_delete]
                
                for file_info in oldest_files:
                    success, _ = self.delete_file(file_info['name'])
                    if success:
                        deleted_count += 1
                        logger.info(f"Deleted excess file: {file_info['name']}")
            
            message = f"Cleanup completed. Deleted {deleted_count} files."
            logger.info(message)
            return deleted_count, message
            
        except Exception as e:
            error_msg = f"Error during cleanup: {str(e)}"
            logger.error(error_msg)
            return 0, error_msg
    
    def get_storage_stats(self):
        """
        Get comprehensive storage statistics
        
        Returns:
            dict: Storage statistics and file counts
        """
        try:
            disk_usage = self.get_disk_usage()
            files = self.get_file_list()
            
            # Calculate file statistics
            total_files = len(files)
            total_file_size = sum(file['size'] for file in files)
            
            # Group by extension
            extensions = {}
            for file in files:
                ext = file['extension']
                if ext not in extensions:
                    extensions[ext] = {'count': 0, 'size': 0}
                extensions[ext]['count'] += 1
                extensions[ext]['size'] += file['size']
            
            return {
                'disk_usage': disk_usage,
                'total_files': total_files,
                'total_file_size': total_file_size,
                'extensions': extensions,
                'average_file_size': total_file_size / total_files if total_files > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {}
    
    def validate_mount_point(self):
        """
        Validate that the USB mount point is accessible and writable
        
        Returns:
            tuple: (is_valid: bool, message: str)
        """
        try:
            # Check if mount point exists
            if not self.usb_drive_mount.exists():
                return False, "Mount point does not exist"
            
            # Check if it's a directory
            if not self.usb_drive_mount.is_dir():
                return False, "Mount point is not a directory"
            
            # Check write permissions by creating a test file
            test_file = self.usb_drive_mount / ".test_write_permission"
            try:
                test_file.write_text("test")
                test_file.unlink()
                return True, "Mount point is accessible and writable"
            except PermissionError:
                return False, "Mount point is not writable"
            except Exception as e:
                return False, f"Write test failed: {str(e)}"
                
        except Exception as e:
            return False, f"Mount point validation error: {str(e)}"