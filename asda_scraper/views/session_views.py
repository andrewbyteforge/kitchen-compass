"""
Session-related views for viewing crawl session details.

File: asda_scraper/views/session_views.py
"""

import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages

from asda_scraper.models import CrawlSession
from .base import is_admin_user, parse_error_message

logger = logging.getLogger(__name__)


@login_required
@user_passes_test(is_admin_user)
def session_detail(request, session_id):
    """
    Detailed view of a specific crawl session.
    
    Args:
        request: Django HttpRequest object
        session_id: ID of the crawl session
        
    Returns:
        HttpResponse: Rendered session detail template
    """
    try:
        session = get_object_or_404(CrawlSession, pk=session_id)
        
        # Parse error log if present
        error_summary = None
        if session.error_log:
            error_summary = parse_error_message(session.error_log)
        
        # Get session statistics
        session_stats = {
            'duration': session.get_duration(),
            'products_per_minute': 0,
            'categories_per_minute': 0,
        }
        
        if session_stats['duration']:
            minutes = session_stats['duration'].total_seconds() / 60
            if minutes > 0:
                session_stats['products_per_minute'] = round(session.products_found / minutes, 1)
                session_stats['categories_per_minute'] = round(session.categories_crawled / minutes, 1)
        
        context = {
            'session': session,
            'error_summary': error_summary,
            'session_stats': session_stats,
        }
        
        return render(request, 'asda_scraper/session_detail.html', context)
        
    except Exception as e:
        logger.error(f"Error loading session detail: {e}")
        messages.error(request, "An error occurred while loading the session details.")
        return redirect('asda_scraper:dashboard')