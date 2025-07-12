"""
Crawl operation views for starting, stopping, and monitoring crawls.

File: asda_scraper/views/crawl_operations.py
"""

import logging
import json
import threading
from typing import Dict, Any
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from asda_scraper.models import AsdaCategory, AsdaProduct, CrawlSession

# Update imports to use the new scrapers package
from asda_scraper.scrapers import (
    create_selenium_scraper, 
    ScrapingResult, 
    ScraperException, 
    DriverSetupException
)

from .base import is_admin_user, check_system_health

logger = logging.getLogger(__name__)


@login_required
@user_passes_test(is_admin_user)
@require_http_methods(["POST"])
def start_crawl(request):
    """
    Start a new crawl session with specified crawl type.
    
    Args:
        request: Django HttpRequest object
        
    Returns:
        JsonResponse: Result of the crawl start attempt
    """
    try:
        # Check if a crawl is already running
        existing_session = CrawlSession.objects.filter(
            status__in=['PENDING', 'RUNNING']
        ).first()
        
        if existing_session:
            return JsonResponse({
                'success': False,
                'message': f'Crawl session {existing_session.pk} is already running'
            })
        
        # Parse crawl settings
        crawl_settings = parse_crawl_settings(request)
        
        # Validate settings
        validation_errors = validate_crawl_settings(crawl_settings)
        if validation_errors:
            return JsonResponse({
                'success': False,
                'message': 'Invalid crawl settings',
                'errors': validation_errors
            })
        
        # Create new crawl session with crawl type
        session = CrawlSession.objects.create(
            user=request.user,
            status='PENDING',
            crawl_type=crawl_settings.get('crawl_type', 'PRODUCT'),
            crawl_settings=crawl_settings
        )
        
        # Start scraper in background thread
        thread = threading.Thread(
            target=run_selenium_scraper_with_error_handling,
            args=(session,)
        )
        thread.daemon = True
        thread.start()
        
        logger.info(
            f"Started {session.crawl_type} crawl session {session.pk} "
            f"by user {request.user.username}"
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{session.get_crawl_type_display()} crawl session {session.pk} started successfully',
            'session_id': session.pk,
            'crawl_type': session.crawl_type
        })
        
    except Exception as e:
        logger.error(f"Error starting crawl session: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Failed to start crawl: {str(e)}'
        })


@login_required
@user_passes_test(is_admin_user)
@require_http_methods(["POST"])
def stop_crawl(request):
    """
    Stop the current crawl session with improved handling.
    
    Args:
        request: Django HttpRequest object
        
    Returns:
        JsonResponse: Result of the stop attempt
    """
    try:
        current_session = CrawlSession.objects.filter(
            status__in=['PENDING', 'RUNNING']
        ).first()
        
        if not current_session:
            return JsonResponse({
                'success': False,
                'message': 'No active crawl session found'
            })
        
        # Mark session as stopped
        current_session.status = 'CANCELLED'
        current_session.end_time = timezone.now()
        if not current_session.error_log:
            current_session.error_log = 'Stopped by user'
        current_session.save()
        
        logger.info(f"Crawl session {current_session.pk} stopped by user {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'message': f'Crawl session {current_session.pk} stopped successfully. '
                      'The browser may continue until the current operation completes.'
        })
        
    except Exception as e:
        logger.error(f"Error stopping crawl session: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Failed to stop crawl: {str(e)}'
        })


@login_required
@user_passes_test(is_admin_user)
def crawl_status(request):
    """
    Get current crawl status via AJAX with crawl type information.
    
    Args:
        request: Django HttpRequest object
        
    Returns:
        JsonResponse: Current crawl status and statistics
    """
    try:
        current_session = CrawlSession.objects.filter(
            status__in=['PENDING', 'RUNNING']
        ).first()
        
        if current_session:
            # Calculate progress percentage
            total_categories = AsdaCategory.objects.filter(is_active=True).count()
            progress_percent = 0
            if total_categories > 0:
                progress_percent = (current_session.categories_crawled / total_categories) * 100
            
            # Estimate remaining time
            duration = current_session.get_duration()
            estimated_remaining = None
            if duration and current_session.categories_crawled > 0:
                time_per_category = duration.total_seconds() / current_session.categories_crawled
                remaining_categories = total_categories - current_session.categories_crawled
                estimated_remaining = time_per_category * remaining_categories
            
            data = {
                'has_session': True,
                'session_id': current_session.pk,
                'status': current_session.status,
                'crawl_type': current_session.crawl_type,
                'crawl_type_display': current_session.get_crawl_type_display(),
                'start_time': current_session.start_time.isoformat(),
                'categories_crawled': current_session.categories_crawled,
                'total_categories': total_categories,
                'progress_percent': round(progress_percent, 1),
                'products_found': current_session.products_found,
                'products_updated': current_session.products_updated,
                'products_with_nutrition': current_session.products_with_nutrition,
                'nutrition_errors': current_session.nutrition_errors,
                'duration': str(duration) if duration else None,
                'estimated_remaining': estimated_remaining,
                'using_selenium': current_session.crawl_settings.get('use_selenium', False),
                'error_log': current_session.error_log,
            }
        else:
            # Get nutrition stats for idle display
            products_with_nutrition = AsdaProduct.objects.filter(
                nutritional_info__isnull=False
            ).count()
            
            data = {
                'has_session': False,
                'total_products': AsdaProduct.objects.count(),
                'total_categories': AsdaCategory.objects.count(),
                'products_with_nutrition': products_with_nutrition,
                'system_health': check_system_health(),
            }
        
        return JsonResponse(data)
        
    except Exception as e:
        logger.error(f"Error getting crawl status: {str(e)}")
        return JsonResponse({
            'error': str(e)
        }, status=500)


# Update the parse_crawl_settings function in asda_scraper/views/crawl_operations.py
# Around line 150

# Replace the parse_crawl_settings function in asda_scraper/views/crawl_operations.py
# Around line 150

def parse_crawl_settings(request) -> Dict[str, Any]:
    """
    Parse crawl settings from request - RESTORED to allow BOTH option.
    
    Args:
        request: Django HttpRequest object
        
    Returns:
        Dict[str, Any]: Parsed crawl settings
    """
    # Default settings
    settings = {
        'crawl_type': 'PRODUCT',
        'max_categories': 10,
        'category_priority': 2,
        'max_products_per_category': 100,
        'delay_between_requests': 2.0,
        'use_selenium': True,
        'headless': False,
        'respect_robots_txt': True,
        'crawl_nutrition': False,
    }
    
    try:
        # Parse form data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        # Handle crawl type - ALLOW ALL OPTIONS
        if 'crawl_type' in data:
            crawl_type = data['crawl_type']
            if crawl_type in ['PRODUCT', 'NUTRITION', 'BOTH']:
                settings['crawl_type'] = crawl_type
                settings['crawl_nutrition'] = crawl_type in ['NUTRITION', 'BOTH']
                logger.info(f"Crawl type set to: {crawl_type}")
            else:
                logger.warning(f"Invalid crawl type: {crawl_type}, defaulting to PRODUCT")
        
        # Update settings with user input
        for key in ['max_categories', 'category_priority', 'max_products_per_category']:
            if key in data:
                try:
                    settings[key] = int(data[key])
                except (ValueError, TypeError):
                    pass
        
        for key in ['delay_between_requests']:
            if key in data:
                try:
                    settings[key] = float(data[key])
                except (ValueError, TypeError):
                    pass
        
        for key in ['headless', 'use_selenium']:
            if key in data:
                settings[key] = str(data.get(key, 'false')).lower() == 'true'
        
        logger.info(f"Final crawl settings: crawl_type={settings['crawl_type']}, crawl_nutrition={settings['crawl_nutrition']}")
        
    except Exception as e:
        logger.warning(f"Error parsing crawl settings: {e}")
    
    return settings





def validate_crawl_settings(settings: Dict[str, Any]) -> list:
    """
    Validate crawl settings.
    
    Args:
        settings: Dictionary of crawl settings
        
    Returns:
        list: List of validation errors
    """
    errors = []
    
    # Validate numeric ranges
    if settings.get('max_categories', 0) <= 0 or settings.get('max_categories', 0) > 50:
        errors.append('max_categories must be between 1 and 50')
    
    if settings.get('category_priority', 0) <= 0 or settings.get('category_priority', 0) > 5:
        errors.append('category_priority must be between 1 and 5')
    
    if settings.get('max_products_per_category', 0) <= 0:
        errors.append('max_products_per_category must be greater than 0')
    
    if settings.get('delay_between_requests', 0) < 0:
        errors.append('delay_between_requests cannot be negative')
    
    return errors


def run_selenium_scraper_with_error_handling(session: CrawlSession):
    """
    Run the Selenium scraper with comprehensive error handling.
    
    Args:
        session: CrawlSession object to process
    """
    scraper = None
    
    try:
        logger.info(f"Starting Selenium scraper for session {session.pk}")
        
        # Get headless setting
        headless = session.crawl_settings.get('headless', False)
        
        # Create and run scraper
        scraper = create_selenium_scraper(session, headless=headless)
        result = scraper.start_crawl()
        
        # Log results
        log_scraping_results(session, result)
        
        # Handle any errors that occurred during scraping
        if result.errors:
            error_summary = create_error_summary(result.errors)
            session.error_log = error_summary
            session.save()
            
            logger.warning(f"Session {session.pk} completed with {len(result.errors)} errors")
        else:
            logger.info(f"Session {session.pk} completed successfully")
        
    except DriverSetupException as e:
        error_msg = f"WebDriver setup failed: {str(e)}"
        logger.error(error_msg)
        session.mark_failed(error_msg)
        
    except ScraperException as e:
        error_msg = f"Scraper error: {str(e)}"
        logger.error(error_msg)
        session.mark_failed(error_msg)
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        session.mark_failed(error_msg)
    
    finally:
        # Ensure proper cleanup
        if scraper:
            try:
                scraper._cleanup()
            except Exception as cleanup_error:
                logger.error(f"Error during scraper cleanup: {cleanup_error}")
        
        # Log final session state
        session.refresh_from_db()
        logger.info(f"Session {session.pk} final status: {session.status}")


def log_scraping_results(session: CrawlSession, result: ScrapingResult):
    """
    Log comprehensive scraping results.
    
    Args:
        session: CrawlSession object
        result: ScrapingResult object
    """
    logger.info(f"Scraping Results for Session {session.pk}:")
    logger.info(f"  Products Found: {result.products_found}")
    logger.info(f"  Products Saved: {result.products_saved}")
    logger.info(f"  Categories Processed: {result.categories_processed}")
    logger.info(f"  Duration: {result.duration:.2f} seconds")
    logger.info(f"  Error Count: {len(result.errors)}")
    
    if result.errors:
        logger.warning("Errors encountered:")
        for i, error in enumerate(result.errors[:5], 1):
            logger.warning(f"  {i}. {error}")
        if len(result.errors) > 5:
            logger.warning(f"  ... and {len(result.errors) - 5} more errors")


def create_error_summary(errors: list) -> str:
    """
    Create a summary of errors for storage.
    
    Args:
        errors: List of error strings
        
    Returns:
        str: Formatted error summary
    """
    if not errors:
        return ""
    
    summary_lines = [f"Total Errors: {len(errors)}", ""]
    
    # Group similar errors
    error_counts = {}
    for error in errors:
        error_type = error.split(':')[0] if ':' in error else 'Unknown'
        error_counts[error_type] = error_counts.get(error_type, 0) + 1
    
    # Add error type summary
    summary_lines.append("Error Types:")
    for error_type, count in sorted(error_counts.items()):
        summary_lines.append(f"  {error_type}: {count}")
    
    # Add first few actual errors
    summary_lines.extend(["", "Sample Errors:"])
    for i, error in enumerate(errors[:3], 1):
        summary_lines.append(f"  {i}. {error}")
    
    if len(errors) > 3:
        summary_lines.append(f"  ... and {len(errors) - 3} more")
    
    return "\n".join(summary_lines)