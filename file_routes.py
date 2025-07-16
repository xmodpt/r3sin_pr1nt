#!/usr/bin/env python3
"""
File Management Routes for Resin Printer Control Application
Contains all Flask routes related to file operations
"""

from flask import Blueprint, request, jsonify, send_from_directory
import logging

logger = logging.getLogger(__name__)

def create_file_routes(file_manager):
    """
    Create Flask blueprint with file management routes
    
    Args:
        file_manager: FileManager instance
        
    Returns:
        Blueprint: Flask blueprint with file routes
    """
    
    file_bp = Blueprint('files', __name__, url_prefix='/api')
    
    @file_bp.route('/files')
    def api_files():
        """Get list of all files on USB drive"""
        try:
            files = file_manager.get_file_list()
            return jsonify(files)
        except Exception as e:
            logger.error(f"Error getting file list: {e}")
            return jsonify({'error': str(e)}), 500
    
    @file_bp.route('/files/<filename>')
    def api_file_info(filename):
        """Get detailed information about a specific file"""
        try:
            file_info = file_manager.get_file_info(filename)
            if file_info:
                return jsonify(file_info)
            else:
                return jsonify({'error': 'File not found'}), 404
        except Exception as e:
            logger.error(f"Error getting file info for {filename}: {e}")
            return jsonify({'error': str(e)}), 500
    
    @file_bp.route('/upload', methods=['POST'])
    def api_upload():
        """Upload one or multiple files to USB drive"""
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': 'No files provided'})
        
        files = request.files.getlist('files')
        uploaded = []
        errors = []
        
        logger.info(f"Processing upload of {len(files)} file(s)")
        
        for file in files:
            if file.filename:
                success, message, saved_filename = file_manager.save_uploaded_file(file)
                
                if success:
                    uploaded.append({
                        'name': saved_filename,
                        'original_name': file.filename,
                        'message': message
                    })
                    logger.info(f"File uploaded successfully: {saved_filename}")
                else:
                    errors.append({
                        'filename': file.filename,
                        'error': message
                    })
                    logger.error(f"Failed to upload {file.filename}: {message}")
            else:
                errors.append({
                    'filename': 'unknown',
                    'error': 'No filename provided'
                })
        
        return jsonify({
            'success': len(uploaded) > 0,
            'uploaded': uploaded,
            'errors': errors,
            'total_uploaded': len(uploaded),
            'total_errors': len(errors)
        })
    
    @file_bp.route('/delete_file', methods=['POST'])
    def api_delete_file():
        """Delete a file from USB drive"""
        data = request.get_json()
        filename = data.get('filename', '')
        
        if not filename:
            return jsonify({'success': False, 'error': 'No filename provided'})
        
        logger.info(f"Attempting to delete file: {filename}")
        
        try:
            success, message = file_manager.delete_file(filename)
            
            if success:
                logger.info(f"File deleted successfully: {filename}")
                return jsonify({'success': True, 'message': message})
            else:
                logger.error(f"Failed to delete file {filename}: {message}")
                return jsonify({'success': False, 'error': message})
                
        except Exception as e:
            logger.error(f"Exception deleting file {filename}: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @file_bp.route('/download/<filename>')
    def api_download(filename):
        """Download a file from USB drive"""
        try:
            if not file_manager.file_exists(filename):
                return jsonify({'error': 'File not found'}), 404
            
            logger.info(f"Serving download for file: {filename}")
            return send_from_directory(
                file_manager.usb_drive_mount, 
                filename, 
                as_attachment=True
            )
            
        except Exception as e:
            logger.error(f"Error serving download for {filename}: {e}")
            return jsonify({'error': str(e)}), 500
    
    @file_bp.route('/storage_stats')
    def api_storage_stats():
        """Get comprehensive storage statistics"""
        try:
            stats = file_manager.get_storage_stats()
            return jsonify(stats)
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return jsonify({'error': str(e)}), 500
    
    @file_bp.route('/validate_storage', methods=['POST'])
    def api_validate_storage():
        """Validate that storage is accessible and writable"""
        try:
            is_valid, message = file_manager.validate_mount_point()
            return jsonify({
                'valid': is_valid,
                'message': message
            })
        except Exception as e:
            logger.error(f"Error validating storage: {e}")
            return jsonify({'error': str(e)}), 500
    
    @file_bp.route('/cleanup_files', methods=['POST'])
    def api_cleanup_files():
        """Clean up old files to free space"""
        data = request.get_json() or {}
        max_files = data.get('max_files', 50)
        max_age_days = data.get('max_age_days', 30)
        
        try:
            deleted_count, message = file_manager.cleanup_old_files(max_files, max_age_days)
            
            return jsonify({
                'success': True,
                'deleted_count': deleted_count,
                'message': message
            })
            
        except Exception as e:
            logger.error(f"Error during file cleanup: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @file_bp.route('/refresh_files', methods=['POST'])
    def api_refresh_files():
        """Force refresh of file list (useful after external changes)"""
        try:
            # Just return fresh file list
            files = file_manager.get_file_list()
            logger.info("File list refreshed")
            return jsonify({
                'success': True,
                'files': files,
                'count': len(files)
            })
        except Exception as e:
            logger.error(f"Error refreshing files: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @file_bp.route('/file_exists/<filename>')
    def api_file_exists(filename):
        """Check if a file exists on USB drive"""
        try:
            exists = file_manager.file_exists(filename)
            return jsonify({'exists': exists})
        except Exception as e:
            logger.error(f"Error checking if file exists {filename}: {e}")
            return jsonify({'error': str(e)}), 500
    
    return file_bp