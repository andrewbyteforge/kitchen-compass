"""
Utility functions for category and subcategory navigation.

Handles discovery and processing of category hierarchies on ASDA website.
"""

import logging
import re
from typing import List, Dict, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains

from ..models import Category, CrawlQueue

logger = logging.getLogger(__name__)


class CategoryNavigator:
    """
    Handles navigation and discovery of category hierarchies.
    
    Discovers subcategories, department links, and category refinements.
    """
    
    def __init__(self, driver: webdriver.Chrome, wait: WebDriverWait):
        """
        Initialize the category navigator.
        
        Args:
            driver: Selenium WebDriver instance
            wait: WebDriverWait instance
        """
        self.driver = driver
        self.wait = wait
        self.discovered_urls: Set[str] = set()



    def _find_explore_sections(self) -> List[Dict[str, str]]:
        """
        Find links in "Explore Aisle" and "Explore Department" sections.
        
        Enhanced to capture specific patterns from ASDA HTML structure:
        - h2.taxonomy-explore__title + ul.taxonomy-explore__list
        - a.asda-btn.asda-btn--light.taxonomy-explore__item
        
        Returns:
            List of explore section dictionaries
        """
        explore_categories = []
        
        try:
            logger.debug("Starting explore sections discovery")
            
            # PRIORITY SELECTORS - Based on HTML analysis
            priority_selectors = [
                # 1. Specific pattern: h2 "Explore departments" + following ul links
                "h2.taxonomy-explore__title + ul.taxonomy-explore__list a",
                "h2:contains('Explore departments') + ul a",
                "h2:contains('Explore') + ul a",
                
                # 2. Direct taxonomy explore items with specific classes
                "a.asda-btn.asda-btn--light.taxonomy-explore__item",
                "a.taxonomy-explore__item[data-auto-id='linkTaxonomyExplore']",
                
                # 3. Any taxonomy explore list items
                "ul.taxonomy-explore__list a",
                ".taxonomy-explore__list a",
            ]
            
            # SECONDARY SELECTORS - General explore patterns
            secondary_selectors = [
                # Explore section containers
                "section[data-auto-id='taxonomyExplore'] a",
                "section.taxonomy-explore a",
                "[class*='explore'] [class*='item'] a",
                
                # Explore containers
                "div.explore-departments a",
                "div.explore-aisles a",
                "div.department-explorer a",
                ".explore-section a",
                
                # Generic explore patterns
                "[class*='explore'] a[href*='/dept/']",
                "[class*='explore'] a[href*='/cat/']",
                "[data-testid*='explore'] a",
                
                # Button-style explore links
                "button[class*='explore'][onclick]",
                "[role='button'][class*='explore']"
            ]
            
            # Combine selectors with priority
            all_selectors = priority_selectors + secondary_selectors
            
            # Track which selectors are finding results
            selector_performance = {}
            
            for selector in all_selectors:
                try:
                    # Handle XPath for contains() selectors
                    if ':contains(' in selector:
                        # Convert CSS :contains() to XPath
                        xpath_selector = self._convert_contains_to_xpath(selector)
                        elements = self.driver.find_elements(By.XPATH, xpath_selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    element_count = len(elements)
                    selector_performance[selector] = element_count
                    
                    if element_count > 0:
                        logger.debug(f"Explore selector '{selector}' found {element_count} elements")
                    
                    for element in elements:
                        try:
                            # Enhanced href extraction
                            href = (element.get_attribute('href') or
                                element.get_attribute('data-href') or
                                element.get_attribute('data-url'))
                            
                            # Enhanced text extraction
                            text = (element.text.strip() or
                                element.get_attribute('title') or
                                element.get_attribute('aria-label') or
                                "").strip()
                            
                            if href and text and self._is_valid_category_url(href):
                                full_url = self._normalize_url(href)
                                
                                if full_url not in self.discovered_urls:
                                    self.discovered_urls.add(full_url)
                                    
                                    # Extract metadata
                                    element_class = element.get_attribute('class') or ''
                                    data_auto_id = element.get_attribute('data-auto-id') or ''
                                    data_di_id = element.get_attribute('data-di-id') or ''
                                    
                                    explore_link = {
                                        'name': text,
                                        'url': full_url,
                                        'selector': selector,
                                        'element_class': element_class,
                                        'data_auto_id': data_auto_id,
                                        'data_di_id': data_di_id,
                                        'type': 'explore_section',
                                        'priority': 100 if selector in priority_selectors else 50
                                    }
                                    
                                    explore_categories.append(explore_link)
                                    logger.debug(f"Found explore link: {text} - {full_url}")
                            
                        except Exception as e:
                            logger.debug(f"Error processing explore element: {str(e)}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"Error with explore selector '{selector}': {str(e)}")
                    continue
            
            # Look for explore sections by finding headers first, then following siblings
            explore_categories.extend(self._find_explore_by_headers())
            
            # Remove duplicates based on URL
            unique_explores = {}
            for explore in explore_categories:
                url = explore['url']
                if url not in unique_explores or explore['priority'] > unique_explores[url]['priority']:
                    unique_explores[url] = explore
            
            explore_categories = list(unique_explores.values())
            
            if explore_categories:
                logger.info(f"Found {len(explore_categories)} explore section links")
                
                # Log top performing selectors
                top_performers = sorted(selector_performance.items(), key=lambda x: x[1], reverse=True)[:3]
                logger.debug("Top explore selectors:")
                for selector, count in top_performers:
                    if count > 0:
                        logger.debug(f"  - '{selector}': {count} elements")
            
            # Sort by priority
            explore_categories.sort(key=lambda x: x['priority'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error finding explore sections: {str(e)}")
        
        return explore_categories

    def _find_explore_by_headers(self) -> List[Dict[str, str]]:
        """
        Find explore sections by locating headers and following sibling links.
        
        Returns:
            List of explore link dictionaries
        """
        explore_links = []
        
        try:
            # Find headers containing "Explore"
            header_xpaths = [
                "//h2[contains(text(), 'Explore departments')]",
                "//h2[contains(text(), 'Explore')]",
                "//h3[contains(text(), 'Explore')]",
                "//*[contains(@class, 'taxonomy-explore__title')]"
            ]
            
            for xpath in header_xpaths:
                try:
                    headers = self.driver.find_elements(By.XPATH, xpath)
                    
                    for header in headers:
                        # Look for following sibling ul or div containing links
                        sibling_selectors = [
                            "./following-sibling::ul//a",
                            "./following-sibling::div//a",
                            "./parent::*/following-sibling::ul//a",
                            "./parent::*/following-sibling::div//a"
                        ]
                        
                        for sibling_selector in sibling_selectors:
                            try:
                                links = header.find_elements(By.XPATH, sibling_selector)
                                
                                for link in links:
                                    href = link.get_attribute('href')
                                    text = link.text.strip()
                                    
                                    if href and text and self._is_valid_category_url(href):
                                        full_url = self._normalize_url(href)
                                        
                                        if full_url not in self.discovered_urls:
                                            explore_links.append({
                                                'name': text,
                                                'url': full_url,
                                                'selector': f"header_sibling:{xpath}",
                                                'type': 'explore_section',
                                                'priority': 95
                                            })
                                            
                                            logger.debug(f"Found explore via header: {text} - {full_url}")
                                            
                            except Exception:
                                continue
                                
                except Exception:
                    continue
                    
        except Exception as e:
            logger.debug(f"Error finding explore by headers: {str(e)}")
        
        return explore_links

    def _convert_contains_to_xpath(self, css_selector: str) -> str:
        """
        Convert CSS selector with :contains() to XPath.
        
        Args:
            css_selector: CSS selector string with :contains()
            
        Returns:
            XPath equivalent
        """
        try:
            # Handle simple cases like "h2:contains('text')"
            if ':contains(' in css_selector:
                parts = css_selector.split(':contains(')
                element = parts[0]
                text_part = parts[1].rstrip(')')
                text_content = text_part.strip("'\"")
                
                return f"//{element}[contains(text(), '{text_content}')]"
            
        except Exception:
            pass
        
        # Fallback to original selector (will likely fail, but logged)
        return css_selector








        
    def discover_all_links(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Discover all types of category links on the current page.
        
        Enhanced to handle inconsistent class naming (taxonomy-explore__item vs taxonomy-exploreitem)
        and ensure comprehensive link discovery.
        
        Returns:
            Dictionary with categorized links:
            - 'subcategories': Regular subcategory links
            - 'explore_sections': Explore aisle/department links
            - 'refinements': Category refinement links
            - 'navigation': Navigation menu links
        """
        logger.info("🔍 Starting comprehensive link discovery...")
        
        all_links = {
            'subcategories': [],
            'explore_sections': [],
            'refinements': [],
            'navigation': []
        }
        
        # Discover regular subcategories (includes most patterns)
        logger.info("   🔸 Discovering subcategories...")
        all_links['subcategories'] = self.discover_subcategories()
        
        # Discover explore sections (specific patterns for explore departments)
        logger.info("   🔸 Discovering explore sections...")
        all_links['explore_sections'] = self._find_explore_sections()
        
        # Discover refinement links
        logger.info("   🔸 Discovering refinement links...")
        all_links['refinements'] = self._find_refinement_links()
        
        # Discover navigation menu links
        logger.info("   🔸 Discovering navigation links...")
        all_links['navigation'] = self._find_navigation_links()
        
        # Remove duplicates between categories
        all_links = self._deduplicate_links(all_links)
        
        # Log comprehensive summary
        total_links = sum(len(links) for links in all_links.values())
        logger.info(f"🎯 LINK DISCOVERY COMPLETE: {total_links} total links found")
        
        for link_type, links in all_links.items():
            if links:
                logger.info(f"   ✅ {link_type}: {len(links)} links")
                # Log first few links for debugging
                for i, link in enumerate(links[:3]):
                    logger.info(f"      {i+1}. {link['name']} -> {link['url']}")
                if len(links) > 3:
                    logger.info(f"      ... and {len(links) - 3} more")
        
        return all_links

    def _deduplicate_links(self, all_links: Dict[str, List[Dict[str, str]]]) -> Dict[str, List[Dict[str, str]]]:
        """
        Remove duplicate URLs across different link categories.
        
        Priority: explore_sections > subcategories > refinements > navigation
        
        Args:
            all_links: Dictionary of categorized links
            
        Returns:
            Dictionary with deduplicated links
        """
        seen_urls = set()
        deduplicated = {
            'subcategories': [],
            'explore_sections': [],
            'refinements': [],
            'navigation': []
        }
        
        # Process in priority order
        priority_order = ['explore_sections', 'subcategories', 'refinements', 'navigation']
        
        for category in priority_order:
            for link in all_links[category]:
                url = link['url']
                if url not in seen_urls:
                    seen_urls.add(url)
                    deduplicated[category].append(link)
        
        return deduplicated














    def discover_subcategories(self) -> List[Dict[str, str]]:
        """
        Discover all subcategory links on the current page.
        
        Enhanced to capture:
        - Department links (/dept/)
        - Category links (/cat/)
        - Aisle links (/aisle/) <- NEW
        - All explore patterns
        
        Returns:
            List of dictionaries containing subcategory information
        """
        subcategories = []
        
        # COMPREHENSIVE SELECTORS - Enhanced with aisle link support
        selectors = [
            # HIGHEST PRIORITY - Explore patterns (departments & aisles)
            
            # 1. Explore departments (existing patterns)
            "ul.taxonomy-explore__list a.asda-btn.asda-btn--light.taxonomy-explore__item",
            "ul.taxonomy-explorelist a.asda-btn.asda-btn--light.taxonomy-exploreitem",
            "ul.taxonomy-explore__list a",
            "ul.taxonomy-explorelist a",
            
            # 2. Explore aisles (NEW PATTERNS)
            "a[href*='/aisle/']",
            "a[href*='aisle']",
            ".aisle-link",
            ".explore-aisle a",
            "a[class*='aisle']",
            
            # 3. All data-auto-id patterns
            "a[data-auto-id='linkTaxonomyExplore']",
            "a[data-auto-id*='aisle']",
            "a[data-auto-id*='explore']",
            
            # 4. Class-based aisle patterns
            "a.taxonomy-explore__item",
            "a.taxonomy-exploreitem", 
            "a.asda-btn.asda-btn--light.taxonomy-explore__item",
            "a.asda-btn.asda-btn--light.taxonomy-exploreitem",
            
            # 5. Header-following patterns
            "h2.taxonomy-explore__title + ul a",
            "h2.taxonomy-exploretitle + ul a",
            "h2:contains('Explore') + ul a",
            "h2:contains('explore') + ul a",
            
            # 6. Generic explore patterns
            ".explore-section a",
            ".explore-departments a",
            ".explore-aisles a",
            "[class*='explore'] a",
            
            # MEDIUM PRIORITY - Department and category patterns
            
            # 7. Department links
            "a[href*='/dept/']:not([href*='product']):not([href*='search'])",
            
            # 8. Category links  
            "a[href*='/cat/']:not([href*='product']):not([href*='search'])",
            
            # 9. Original working patterns
            "[class*='-taxo'] a",
            ".category-navigation a",
            "[data-testid*='category'] a",
            
            # 10. Data attribute patterns
            "a[data-di-id*='di-id-'][href*='/dept/']",
            "a[data-di-id*='di-id-'][href*='/aisle/']",  # NEW
            "a[data-di-id][href*='/dept/']",
            "a[data-di-id][href*='/aisle/']",  # NEW
            
            # LOW PRIORITY - Generic fallback patterns
            
            # 11. Generic ASDA links
            "a[href*='groceries.asda.com/dept/']",
            "a[href*='groceries.asda.com/aisle/']",  # NEW
            "a[href*='groceries.asda.com/cat/']",
            
            # 12. Button and tile patterns
            "a.department-tile__link",
            "a.category-tile__link",
            "a.aisle-tile__link",  # NEW
            "[data-testid='department-card'] a",
            "[data-testid='aisle-card'] a",  # NEW
            
            # 13. Navigation patterns
            "a.department-nav__link",
            "a.aisle-nav__link",  # NEW
            "a[data-auto-id='linkDepartment']",
            "a[data-auto-id='linkCategory']",
            "a[data-auto-id='linkAisle']",  # NEW
        ]
        
        logger.info(f"🔍 Enhanced discovery with aisle support - {len(selectors)} patterns")
        
        # Track what we find
        selector_results = {}
        found_by_url_type = {'dept': 0, 'cat': 0, 'aisle': 0, 'other': 0}
        
        for i, selector in enumerate(selectors):
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                element_count = len(elements)
                selector_results[selector] = element_count
                
                if element_count > 0:
                    logger.info(f"   [{i+1:2d}] ✅ '{selector}': {element_count} elements")
                
                for element in elements:
                    try:
                        # Extract URL and text
                        href = (element.get_attribute('href') or
                            element.get_attribute('data-href') or
                            element.get_attribute('data-url'))
                        
                        text = (element.text.strip() or
                            element.get_attribute('title') or
                            element.get_attribute('alt') or
                            element.get_attribute('aria-label') or
                            "").strip()
                        
                        if not href or not text:
                            continue
                        
                        # Validate URL (now includes aisle support)
                        if self._is_valid_category_url(href):
                            full_url = self._normalize_url(href)
                            
                            # Track URL types
                            if '/dept/' in full_url:
                                found_by_url_type['dept'] += 1
                            elif '/cat/' in full_url:
                                found_by_url_type['cat'] += 1
                            elif '/aisle/' in full_url:
                                found_by_url_type['aisle'] += 1
                            else:
                                found_by_url_type['other'] += 1
                            
                            # Check for duplicates
                            if full_url not in self.discovered_urls:
                                self.discovered_urls.add(full_url)
                                
                                # Extract metadata
                                element_class = element.get_attribute('class') or ''
                                data_auto_id = element.get_attribute('data-auto-id') or ''
                                data_di_id = element.get_attribute('data-di-id') or ''
                                
                                # Enhanced link type detection
                                link_type = self._determine_enhanced_link_type(
                                    element_class, selector, data_auto_id, full_url
                                )
                                
                                subcategory = {
                                    'name': text,
                                    'url': full_url,
                                    'selector': selector,
                                    'element_class': element_class,
                                    'data_auto_id': data_auto_id,
                                    'data_di_id': data_di_id,
                                    'type': link_type,
                                    'priority': self._get_enhanced_link_priority(
                                        selector, element_class, data_auto_id, full_url
                                    )
                                }
                                
                                subcategories.append(subcategory)
                                
                                # Enhanced logging with URL type
                                url_type_icon = self._get_url_type_icon(full_url)
                                logger.info(f"      {url_type_icon} FOUND {link_type.upper()}: '{text}'")
                            
                    except Exception as e:
                        logger.debug(f"Error processing element: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.debug(f"Error with selector '{selector}': {str(e)}")
                continue
        
        # Enhanced results summary
        total_found = len(subcategories)
        logger.info(f"🎯 ENHANCED DISCOVERY COMPLETE: {total_found} total links found")
        
        # Log by URL type
        logger.info("📊 BREAKDOWN BY URL TYPE:")
        if found_by_url_type['dept'] > 0:
            logger.info(f"   🏢 Department (/dept/): {found_by_url_type['dept']} links")
        if found_by_url_type['cat'] > 0:
            logger.info(f"   📁 Category (/cat/): {found_by_url_type['cat']} links")
        if found_by_url_type['aisle'] > 0:
            logger.info(f"   🛒 Aisle (/aisle/): {found_by_url_type['aisle']} links")  # NEW
        if found_by_url_type['other'] > 0:
            logger.info(f"   ❓ Other: {found_by_url_type['other']} links")
        
        # Sort by priority
        subcategories.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        return subcategories

    def _determine_enhanced_link_type(self, element_class: str, selector: str, data_auto_id: str, url: str) -> str:
        """
        Enhanced link type detection including aisle support.
        
        Args:
            element_class: CSS class string
            selector: CSS selector used
            data_auto_id: data-auto-id attribute
            url: Full URL
            
        Returns:
            String indicating link type
        """
        element_class = element_class.lower()
        selector = selector.lower()
        data_auto_id = data_auto_id.lower()
        url = url.lower()
        
        # URL-based detection (most reliable)
        if '/aisle/' in url:
            return 'aisle'
        elif '/dept/' in url:
            return 'department'
        elif '/cat/' in url:
            return 'category'
        
        # Class/selector-based detection
        if ('taxonomy-explore' in element_class or 'taxonomy-explore' in selector) and 'linktaxonomyexplore' in data_auto_id:
            return 'explore_department'
        elif 'aisle' in element_class or 'aisle' in selector:
            return 'aisle'
        elif 'taxonomy-explore' in element_class or 'taxonomy-explore' in selector:
            return 'taxonomy_explore'
        elif 'linktaxonomyexplore' in data_auto_id:
            return 'explore_section'
        elif 'department' in element_class or 'department' in selector:
            return 'department'
        elif 'category' in element_class or 'category' in selector:
            return 'category'
        else:
            return 'subcategory'

    def _get_enhanced_link_priority(self, selector: str, element_class: str, data_auto_id: str, url: str) -> int:
        """
        Enhanced priority scoring including aisle links.
        
        Args:
            selector: CSS selector
            element_class: Element classes
            data_auto_id: data-auto-id attribute
            url: Full URL
            
        Returns:
            Priority score
        """
        priority = 0
        
        # HIGHEST priority for aisle links (they contain products)
        if '/aisle/' in url.lower():
            priority += 300
        
        # Very high priority for explore departments
        elif ('taxonomy-explore' in selector and 'asda-btn--light' in selector):
            priority += 200
        elif 'taxonomy-explore' in selector and 'linktaxonomyexplore' in data_auto_id.lower():
            priority += 190
        
        # High priority for department links
        elif '/dept/' in url.lower():
            priority += 100
        
        # Medium priority for category links
        elif '/cat/' in url.lower():
            priority += 80
        
        # Standard patterns
        elif 'taxonomy-explore' in selector:
            priority += 70
        elif 'linktaxonomyexplore' in data_auto_id.lower():
            priority += 60
        
        # Bonus for structured data
        if 'data-auto-id' in selector:
            priority += 10
        if 'data-di-id' in selector:
            priority += 5
        
        return priority

    def _get_url_type_icon(self, url: str) -> str:
        """Get icon for URL type for logging."""
        url = url.lower()
        if '/aisle/' in url:
            return '🛒'
        elif '/dept/' in url:
            return '🏢'
        elif '/cat/' in url:
            return '📁'
        else:
            return '🔗'
        
    def _determine_link_type(self, element_class: str, selector: str, data_auto_id: str) -> str:
        """
        Determine the type of link based on class, selector, and data attributes.
        
        Enhanced to handle both underscore and non-underscore variations.
        
        Args:
            element_class: CSS class string from element
            selector: CSS selector used to find element
            data_auto_id: data-auto-id attribute value
            
        Returns:
            String indicating link type
        """
        element_class = element_class.lower()
        selector = selector.lower()
        data_auto_id = data_auto_id.lower()
        
        # High priority types based on your HTML (handle both variations)
        if ('taxonomy-explore' in element_class or 'taxonomy-explore' in selector) and 'linktaxonomyexplore' in data_auto_id:
            return 'explore_department'
        elif 'taxonomy-explore' in element_class or 'taxonomy-explore' in selector:
            return 'taxonomy_explore'
        elif 'linktaxonomyexplore' in data_auto_id:
            return 'explore_section'
        elif 'department' in element_class or 'department' in selector:
            return 'department'
        elif 'category' in element_class or 'category' in selector:
            return 'category'
        elif 'explore' in element_class or 'explore' in selector:
            return 'explore_section'
        else:
            return 'subcategory'

    def _get_link_priority(self, selector: str, element_class: str, data_auto_id: str) -> int:
        """
        Assign priority score to links for sorting.
        
        Enhanced to handle both underscore and non-underscore variations.
        
        Args:
            selector: CSS selector used
            element_class: Element CSS classes
            data_auto_id: data-auto-id attribute value
            
        Returns:
            Priority score (higher = more important)
        """
        priority = 0
        
        # HIGHEST priority for explore departments patterns (both variations)
        if ('ul.taxonomy-explore__list' in selector or 'ul.taxonomy-explorelist' in selector) and 'asda-btn--light' in selector:
            priority += 200
        elif ('taxonomy-explore' in selector or 'taxonomy-explore' in selector) and 'linktaxonomyexplore' in data_auto_id.lower():
            priority += 190
        elif 'taxonomy-explore' in selector and 'linktaxonomyexplore' in data_auto_id.lower():
            priority += 180
        
        # High priority patterns
        elif 'taxonomy-explore' in selector:
            priority += 100
        elif 'linktaxonomyexplore' in data_auto_id.lower():
            priority += 90
        
        # Medium priority patterns
        elif 'department' in selector or 'department' in element_class:
            priority += 60
        elif 'category' in selector or 'category' in element_class:
            priority += 50
        
        # Bonus for data attributes (more structured)
        if 'data-auto-id' in selector:
            priority += 10
        if 'data-di-id' in selector:
            priority += 5
        
        return priority

    def _find_explore_sections(self) -> List[Dict[str, str]]:
        """
        Find links in "Explore Department" and "Explore Aisles" sections.
        
        Enhanced to capture both department and aisle explore sections with your exact HTML patterns.
        
        Returns:
            List of explore section dictionaries
        """
        explore_categories = []
        
        try:
            logger.debug("🔍 Starting explore sections discovery (departments & aisles)")
            
            # PRIORITY SELECTORS - Based on your exact HTML patterns
            priority_selectors = [
                # 1. Exact patterns from your HTML - BOTH departments and aisles
                "ul.taxonomy-explore__list a.asda-btn.asda-btn--light.taxonomy-explore__item",
                "ul.taxonomy-explore__list a[data-auto-id='linkTaxonomyExplore']",
                "ul.taxonomy-explore__list a",
                
                # 2. Header-specific patterns for BOTH types
                "h2.taxonomy-explore__title + ul.taxonomy-explore__list a",  # Generic header
                "h2:contains('Explore departments') + ul a",                 # Department header
                "h2:contains('Explore aisles') + ul a",                     # Aisle header (NEW)
                
                # 3. All taxonomy explore items regardless of context
                "a.asda-btn.asda-btn--light.taxonomy-explore__item[data-auto-id='linkTaxonomyExplore']",
                "a.taxonomy-explore__item[data-auto-id='linkTaxonomyExplore']",
                
                # 4. Direct aisle URL targeting
                "a[href*='/aisle/'][data-auto-id='linkTaxonomyExplore']",
                "a[href*='/aisle/'].taxonomy-explore__item",
            ]
            
            # SECONDARY SELECTORS - General patterns as fallback
            secondary_selectors = [
                # Any explore section containers
                "section[data-auto-id='taxonomyExplore'] a",
                "section.taxonomy-explore a",
                
                # Generic explore patterns
                "[class*='explore'] a[href*='/dept/']",
                "[class*='explore'] a[href*='/aisle/']",  # NEW
                "[data-testid*='explore'] a",
                
                # All linkTaxonomyExplore items
                "a[data-auto-id='linkTaxonomyExplore']",
            ]
            
            # Combine selectors with priority
            all_selectors = priority_selectors + secondary_selectors
            
            # Track performance
            selector_performance = {}
            found_by_type = {'department': 0, 'aisle': 0, 'other': 0}
            
            for selector in all_selectors:
                try:
                    # Handle XPath selectors for :contains()
                    if ':contains(' in selector:
                        xpath_selector = self._convert_contains_to_xpath(selector)
                        elements = self.driver.find_elements(By.XPATH, xpath_selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    element_count = len(elements)
                    selector_performance[selector] = element_count
                    
                    if element_count > 0:
                        logger.info(f"🎯 Explore selector '{selector}': {element_count} elements")
                    
                    for element in elements:
                        try:
                            href = (element.get_attribute('href') or
                                element.get_attribute('data-href') or
                                element.get_attribute('data-url'))
                            
                            text = (element.text.strip() or
                                element.get_attribute('title') or
                                element.get_attribute('aria-label') or
                                "").strip()
                            
                            if href and text and self._is_valid_category_url(href):
                                full_url = self._normalize_url(href)
                                
                                if full_url not in self.discovered_urls:
                                    self.discovered_urls.add(full_url)
                                    
                                    # Extract metadata
                                    element_class = element.get_attribute('class') or ''
                                    data_auto_id = element.get_attribute('data-auto-id') or ''
                                    data_di_id = element.get_attribute('data-di-id') or ''
                                    
                                    # Determine if this is department or aisle
                                    if '/aisle/' in full_url:
                                        explore_type = 'aisle'
                                        found_by_type['aisle'] += 1
                                        icon = '🛒'
                                    elif '/dept/' in full_url:
                                        explore_type = 'department'
                                        found_by_type['department'] += 1
                                        icon = '🏢'
                                    else:
                                        explore_type = 'other'
                                        found_by_type['other'] += 1
                                        icon = '🔗'
                                    
                                    explore_link = {
                                        'name': text,
                                        'url': full_url,
                                        'selector': selector,
                                        'element_class': element_class,
                                        'data_auto_id': data_auto_id,
                                        'data_di_id': data_di_id,
                                        'type': f'explore_{explore_type}',
                                        'priority': 150 if '/aisle/' in full_url else 100  # Aisles get higher priority
                                    }
                                    
                                    explore_categories.append(explore_link)
                                    logger.info(f"      {icon} FOUND EXPLORE {explore_type.upper()}: '{text}'")
                            
                        except Exception as e:
                            logger.debug(f"Error processing explore element: {str(e)}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"Error with explore selector '{selector}': {str(e)}")
                    continue
            
            # Remove duplicates based on URL (keep highest priority)
            unique_explores = {}
            for explore in explore_categories:
                url = explore['url']
                if url not in unique_explores or explore['priority'] > unique_explores[url]['priority']:
                    unique_explores[url] = explore
            
            explore_categories = list(unique_explores.values())
            
            # Enhanced summary logging
            if explore_categories:
                total_found = len(explore_categories)
                logger.info(f"🎯 EXPLORE SECTIONS FOUND: {total_found} total")
                
                # Breakdown by type
                logger.info("📊 EXPLORE BREAKDOWN:")
                if found_by_type['aisle'] > 0:
                    logger.info(f"   🛒 Aisles: {found_by_type['aisle']} links")
                if found_by_type['department'] > 0:
                    logger.info(f"   🏢 Departments: {found_by_type['department']} links")
                if found_by_type['other'] > 0:
                    logger.info(f"   🔗 Other: {found_by_type['other']} links")
                
                # Show first few for verification
                logger.info("📋 SAMPLE LINKS:")
                for i, explore in enumerate(explore_categories[:3]):
                    icon = '🛒' if '/aisle/' in explore['url'] else '🏢'
                    logger.info(f"   {icon} {explore['name']} -> {explore['url']}")
                if len(explore_categories) > 3:
                    logger.info(f"   ... and {len(explore_categories) - 3} more")
            else:
                logger.warning("❌ NO EXPLORE SECTIONS FOUND")
                
                # Debug: Check what explore-related elements exist
                debug_checks = [
                    ("h2.taxonomy-explore__title", "Explore headers"),
                    ("ul.taxonomy-explore__list", "Explore lists"),
                    ("a.taxonomy-explore__item", "Explore items"),
                    ("a[data-auto-id='linkTaxonomyExplore']", "LinkTaxonomyExplore links"),
                    ("a[href*='/aisle/']", "Aisle links"),
                    ("a[href*='/dept/']", "Department links")
                ]
                
                logger.info("🔍 DEBUG - Checking for explore elements:")
                for selector, description in debug_checks:
                    try:
                        count = len(self.driver.find_elements(By.CSS_SELECTOR, selector))
                        logger.info(f"   {description}: {count} found")
                    except Exception:
                        logger.info(f"   {description}: Error checking")
            
            # Sort by priority (aisles first, then departments)
            explore_categories.sort(key=lambda x: x['priority'], reverse=True)
            
        except Exception as e:
            logger.error(f"❌ Error finding explore sections: {str(e)}")
        
        return explore_categories

    def _convert_contains_to_xpath(self, css_selector: str) -> str:
        """
        Convert CSS selector with :contains() to XPath.
        
        Args:
            css_selector: CSS selector string with :contains()
            
        Returns:
            XPath equivalent
        """
        try:
            if ':contains(' in css_selector:
                # Handle patterns like "h2:contains('Explore aisles') + ul a"
                if ' + ' in css_selector:
                    parts = css_selector.split(' + ')
                    header_part = parts[0]  # "h2:contains('Explore aisles')"
                    following_part = parts[1]  # "ul a"
                    
                    if ':contains(' in header_part:
                        element_and_text = header_part.split(':contains(')
                        element = element_and_text[0]  # "h2"
                        text_part = element_and_text[1].rstrip(')')
                        text_content = text_part.strip("'\"")
                        
                        return f"//{element}[contains(text(), '{text_content}')]/following-sibling::{following_part.replace(' ', '//')}"
                
                # Handle simple patterns like "h2:contains('text')"
                else:
                    parts = css_selector.split(':contains(')
                    element = parts[0]
                    text_part = parts[1].rstrip(')')
                    text_content = text_part.strip("'\"")
                    
                    return f"//{element}[contains(text(), '{text_content}')]"
            
        except Exception as e:
            logger.debug(f"Error converting selector to XPath: {str(e)}")
        
        # Fallback to original selector
        return css_selector












    def _find_explore_by_headers(self) -> List[Dict[str, str]]:
        """
        Find explore sections by locating headers and following sibling links.
        
        This specifically looks for "Explore departments" headers from your HTML.
        
        Returns:
            List of explore link dictionaries
        """
        explore_links = []
        
        try:
            # Find headers containing "Explore" - targeting your specific HTML pattern
            header_xpaths = [
                "//h2[contains(text(), 'Explore departments')]",
                "//h2[contains(text(), 'Explore')]",
                "//h3[contains(text(), 'Explore')]",
                "//*[contains(@class, 'taxonomy-explore__title')]"
            ]
            
            for xpath in header_xpaths:
                try:
                    headers = self.driver.find_elements(By.XPATH, xpath)
                    
                    for header in headers:
                        # Look for following sibling ul or div containing links
                        sibling_selectors = [
                            "./following-sibling::ul//a",
                            "./following-sibling::div//a",
                            "./parent::*/following-sibling::ul//a",
                            "./parent::*/following-sibling::div//a"
                        ]
                        
                        for sibling_selector in sibling_selectors:
                            try:
                                links = header.find_elements(By.XPATH, sibling_selector)
                                
                                for link in links:
                                    href = link.get_attribute('href')
                                    text = link.text.strip()
                                    
                                    if href and text and self._is_valid_category_url(href):
                                        full_url = self._normalize_url(href)
                                        
                                        if full_url not in self.discovered_urls:
                                            explore_links.append({
                                                'name': text,
                                                'url': full_url,
                                                'selector': f"header_sibling:{xpath}",
                                                'type': 'explore_section',
                                                'priority': 95
                                            })
                                            
                                            logger.debug(f"Found explore via header: {text} - {full_url}")
                                            
                            except Exception:
                                continue
                                
                except Exception:
                    continue
                    
        except Exception as e:
            logger.debug(f"Error finding explore by headers: {str(e)}")
        
        return explore_links

    def _find_refinement_links(self) -> List[Dict[str, str]]:
        """
        Find category refinement links (filters, facets).
        
        Returns:
            List of refinement link dictionaries
        """
        refinements = []
        
        refinement_selectors = [
            # Facet filters
            "[data-testid='facet'] a",
            ".facet-list a",
            ".filter-options a",
            
            # Refinement panels
            ".refinement-panel a",
            "[class*='refinement'] a",
            
            # Category filters
            ".category-filters a",
            "[data-auto-id*='filter'] a"
        ]
        
        for selector in refinement_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    href = element.get_attribute('href')
                    text = element.text.strip()
                    
                    if href and text and self._is_valid_category_url(href):
                        full_url = self._normalize_url(href)
                        
                        if full_url not in self.discovered_urls:
                            self.discovered_urls.add(full_url)
                            
                            refinements.append({
                                'name': text,
                                'url': full_url,
                                'selector': selector,
                                'type': 'refinement'
                            })
            except Exception:
                continue
                
        return refinements
    
    def _find_navigation_links(self) -> List[Dict[str, str]]:
        """
        Find links in navigation menus.
        
        Returns:
            List of navigation link dictionaries
        """
        nav_links = []
        
        nav_selectors = [
            # Main navigation
            "nav.main-nav a",
            "[role='navigation'] a",
            
            # Dropdown menus
            ".dropdown-menu a",
            "[class*='menu'] [class*='item'] a",
            
            # Mobile navigation
            ".mobile-nav a",
            "[data-testid='mobile-menu'] a"
        ]
        
        for selector in nav_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    href = element.get_attribute('href')
                    text = element.text.strip()
                    
                    if href and text and self._is_valid_category_url(href):
                        full_url = self._normalize_url(href)
                        
                        if full_url not in self.discovered_urls:
                            self.discovered_urls.add(full_url)
                            
                            nav_links.append({
                                'name': text,
                                'url': full_url,
                                'selector': selector,
                                'type': 'navigation'
                            })
            except Exception:
                continue
                
        return nav_links
    
    def _is_valid_category_url(self, url: str) -> bool:
        """
        Check if URL is a valid category/department/aisle URL.
        
        Enhanced to handle all ASDA link types:
        - /dept/ (department pages)
        - /cat/ (category pages)  
        - /aisle/ (aisle pages) <- NEW
        
        Args:
            url: URL to validate
            
        Returns:
            bool: True if valid category URL
        """
        if not url:
            return False
            
        # Category URL patterns - ENHANCED with aisle support
        valid_patterns = [
            '/dept/',
            '/cat/',
            '/category/',
            '/aisle/',      # NEW: Aisle pages
            'taxonomy',
            'department',
            '/shop/'
        ]
        
        # Invalid patterns (product pages, etc.)
        invalid_patterns = [
            '/product/',
            '/search',
            '#',
            'javascript:',
            '.pdf',
            'login',
            'register',
            'basket',
            'checkout',
            'account',
            'help',
            'store-locator',
            'mailto:',
            'tel:'
        ]
        
        url_lower = url.lower()
        
        # Check for invalid patterns
        if any(pattern in url_lower for pattern in invalid_patterns):
            return False
            
        # Must be ASDA domain or relative URL
        if 'asda.com' not in url_lower and not url.startswith('/'):
            return False
            
        # Check for valid patterns
        is_valid = any(pattern in url_lower for pattern in valid_patterns)
        
        if is_valid:
            logger.debug(f"✅ Valid category URL: {url}")
        else:
            logger.debug(f"❌ Invalid category URL: {url}")
        
        return is_valid











    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL to full absolute URL.
        
        Args:
            url: URL to normalize
            
        Returns:
            str: Normalized URL
        """
        if url.startswith('http'):
            return url
            
        # Handle protocol-relative URLs
        if url.startswith('//'):
            return 'https:' + url
            
        # Get current page URL for base
        current_url = self.driver.current_url
        return urljoin(current_url, url)
    
    def save_subcategories_to_queue(
        self, 
        subcategories: List[Dict[str, str]], 
        parent_category: Optional[Category] = None,
        priority: int = 5
    ) -> int:
        """
        Save discovered subcategories to the crawl queue.
        
        Enhanced with much higher priorities for aisle links to ensure immediate processing.
        
        Args:
            subcategories: List of subcategory dictionaries
            parent_category: Parent category if applicable
            priority: Base queue priority (lower number = higher priority)
            
        Returns:
            int: Number of subcategories added to queue
        """
        added_count = 0
        
        for subcat in subcategories:
            try:
                # Determine category level
                if parent_category:
                    level = parent_category.level + 1
                else:
                    # Estimate level from URL structure
                    url_parts = subcat['url'].split('/')
                    dept_count = url_parts.count('dept')
                    cat_count = url_parts.count('cat')
                    aisle_count = url_parts.count('aisle')
                    level = dept_count + cat_count + aisle_count
                
                # Create or get category record
                category, created = Category.objects.get_or_create(
                    url=subcat['url'],
                    defaults={
                        'name': subcat['name'],
                        'parent': parent_category,
                        'level': level,
                        'is_active': True
                    }
                )
                
                # Add to crawl queue if not already processed
                from .base_scraper import BaseScraper
                url_hash = BaseScraper.get_url_hash(None, subcat['url'])
                
                # ENHANCED PRIORITY SYSTEM - Much higher priorities for aisle links
                adjusted_priority = priority
                
                # HIGHEST PRIORITY: Aisle links (contain products)
                if '/aisle/' in subcat['url']:
                    adjusted_priority = -50  # Very high priority (negative = highest)
                    logger.info(f"🛒 AISLE LINK - Setting HIGHEST priority: {adjusted_priority}")
                    
                # HIGH PRIORITY: Explore sections
                elif subcat.get('type') in ['explore_section', 'explore_department', 'explore_aisle']:
                    adjusted_priority = -20  # High priority
                    logger.info(f"🔍 EXPLORE SECTION - Setting high priority: {adjusted_priority}")
                    
                # MEDIUM PRIORITY: Department links
                elif '/dept/' in subcat['url']:
                    adjusted_priority = -10  # Medium-high priority
                    
                # STANDARD PRIORITY: Category and other links
                elif subcat.get('type') == 'refinement':
                    adjusted_priority += 10  # Lower priority for refinements
                
                # Check if already in queue
                queue_item, queue_created = CrawlQueue.objects.get_or_create(
                    url_hash=url_hash,
                    queue_type='PRODUCT_LIST',
                    defaults={
                        'url': subcat['url'],
                        'priority': adjusted_priority,
                        'category': category,
                        'metadata': {
                            'category_name': subcat['name'],
                            'discovery_type': subcat.get('type', 'subcategory'),
                            'parent_category': parent_category.name if parent_category else None,
                            'selector_used': subcat.get('selector', 'unknown'),
                            'url_type': 'aisle' if '/aisle/' in subcat['url'] else 'dept' if '/dept/' in subcat['url'] else 'category'
                        }
                    }
                )
                
                if queue_created:
                    added_count += 1
                    
                    # Enhanced logging with priority and type
                    url_type_icon = self._get_url_type_icon(subcat['url'])
                    priority_desc = self._get_priority_description(adjusted_priority)
                    
                    logger.info(
                        f"{url_type_icon} Added {subcat.get('type', 'subcategory')} to queue: "
                        f"{subcat['name']} (Priority: {adjusted_priority} - {priority_desc})"
                    )
                    
                    # Special logging for aisle links
                    if '/aisle/' in subcat['url']:
                        logger.info(f"   🎯 AISLE LINK QUEUED FOR IMMEDIATE PROCESSING!")
                        
            except Exception as e:
                logger.error(f"Error saving subcategory {subcat['name']}: {str(e)}")
                
        return added_count

    def _get_url_type_icon(self, url: str) -> str:
        """Get icon for URL type for logging."""
        url = url.lower()
        if '/aisle/' in url:
            return '🛒'
        elif '/dept/' in url:
            return '🏢'
        elif '/cat/' in url:
            return '📁'
        else:
            return '🔗'

    def _get_priority_description(self, priority: int) -> str:
        """Get human-readable priority description."""
        if priority <= -40:
            return "CRITICAL"
        elif priority <= -20:
            return "VERY HIGH"
        elif priority <= -10:
            return "HIGH"
        elif priority <= 0:
            return "MEDIUM"
        elif priority <= 10:
            return "LOW"
        else:
            return "VERY LOW"
    





    
    def check_for_pagination_categories(self) -> bool:
        """
        Check if there are additional category pages (pagination).
        
        Returns:
            bool: True if more category pages exist
        """
        pagination_selectors = [
            "a.pagination__next:not(.disabled)",
            "button.load-more-categories",
            "a[aria-label='Next page categories']",
            "[data-testid='pagination-next']",
            ".category-pagination .next"
        ]
        
        for selector in pagination_selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if element and element.is_enabled():
                    return True
            except NoSuchElementException:
                continue
                
        return False
    
    def get_category_breadcrumbs(self) -> List[Dict[str, str]]:
        """
        Extract category hierarchy from breadcrumbs.
        
        Returns:
            List of breadcrumb items with name and URL
        """
        breadcrumbs = []
        
        breadcrumb_selectors = [
            "nav.breadcrumb a",
            "ol.breadcrumb li a",
            "[data-testid='breadcrumb'] a",
            "[data-auto-id='breadcrumb'] a",
            ".breadcrumb-item a",
            "[aria-label='breadcrumb'] a"
        ]
        
        for selector in breadcrumb_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    for element in elements:
                        href = element.get_attribute('href')
                        text = element.text.strip()
                        
                        if href and text:
                            breadcrumbs.append({
                                'name': text,
                                'url': self._normalize_url(href)
                            })
                    break
            except NoSuchElementException:
                continue
                
        return breadcrumbs
    
    def get_category_info(self) -> Dict[str, any]:
        """
        Extract current category information from the page.
        
        Returns:
            Dictionary containing category details
        """
        info = {
            'name': None,
            'description': None,
            'product_count': None,
            'breadcrumbs': [],
            'has_products': False,
            'has_subcategories': False
        }
        
        # Try to get category name
        name_selectors = [
            "h1.category-title",
            "h1[data-auto-id='categoryTitle']",
            ".category-header h1",
            "[data-testid='category-name']",
            "h1"
        ]
        
        for selector in name_selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if element and element.text.strip():
                    info['name'] = element.text.strip()
                    break
            except NoSuchElementException:
                continue
        
        # Try to get product count
        count_selectors = [
            "[data-auto-id='productCount']",
            "[data-testid='product-count']",
            ".product-count",
            ".results-count",
            "[class*='result'][class*='count']"
        ]
        
        for selector in count_selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = element.text
                # Extract number from text like "324 products" or "Showing 1-24 of 156"
                match = re.search(r'(?:of\s+)?(\d+)(?:\s+products?)?', text, re.IGNORECASE)
                if match:
                    info['product_count'] = int(match.group(1))
                    info['has_products'] = True
                    break
            except NoSuchElementException:
                continue
        
        # Check for products on page
        product_selectors = [
            "[data-testid='product-tile']",
            "[class*='product-tile']",
            "[class*='product-card']",
            "article[class*='product']"
        ]
        
        for selector in product_selectors:
            try:
                products = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if products:
                    info['has_products'] = True
                    if not info['product_count']:
                        info['product_count'] = len(products)
                    break
            except NoSuchElementException:
                continue
        
        # Check for subcategories
        if self.discover_subcategories():
            info['has_subcategories'] = True
        
        # Get breadcrumbs
        info['breadcrumbs'] = self.get_category_breadcrumbs()
        
        return info
    
    def handle_dynamic_content(self) -> None:
        """
        Handle dynamic content loading (infinite scroll, lazy loading).
        """
        try:
            # Scroll to bottom to trigger lazy loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait for new content
            import time
            time.sleep(2)
            
            # Check for "Load More" buttons
            load_more_selectors = [
                "button[class*='load-more']",
                "[data-testid='load-more']",
                "button:contains('Show more')",
                "a.show-more"
            ]
            
            for selector in load_more_selectors:
                try:
                    button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if button.is_displayed() and button.is_enabled():
                        button.click()
                        time.sleep(2)
                        logger.info("Clicked 'Load More' button")
                except NoSuchElementException:
                    continue
                    
        except Exception as e:
            logger.debug(f"Error handling dynamic content: {str(e)}")




    def debug_page_structure(self) -> None:
        """
        Debug method to inspect the current page structure and find all potential links.
        
        This will help identify the correct selectors for ASDA category pages.
        """
        logger.info("="*60)
        logger.info("DEBUG: INSPECTING PAGE STRUCTURE")
        logger.info("="*60)
        
        current_url = self.driver.current_url
        logger.info(f"Current URL: {current_url}")
        
        # Get page title
        try:
            title = self.driver.title
            logger.info(f"Page Title: {title}")
        except Exception:
            pass
        
        # Find all links on the page
        try:
            all_links = self.driver.find_elements(By.TAG_NAME, "a")
            logger.info(f"Total links found on page: {len(all_links)}")
            
            # Categorize links
            dept_links = []
            asda_links = []
            
            for link in all_links:
                try:
                    href = link.get_attribute('href')
                    text = link.text.strip()
                    classes = link.get_attribute('class') or ''
                    data_auto_id = link.get_attribute('data-auto-id') or ''
                    data_di_id = link.get_attribute('data-di-id') or ''
                    
                    if href and '/dept/' in href:
                        dept_links.append({
                            'text': text,
                            'href': href,
                            'classes': classes,
                            'data_auto_id': data_auto_id,
                            'data_di_id': data_di_id
                        })
                    elif href and 'asda.com' in href and text:
                        asda_links.append({
                            'text': text,
                            'href': href,
                            'classes': classes,
                            'data_auto_id': data_auto_id,
                            'data_di_id': data_di_id
                        })
                        
                except Exception:
                    continue
            
            logger.info(f"Department links (/dept/) found: {len(dept_links)}")
            for i, link in enumerate(dept_links[:10]):  # Show first 10
                logger.info(f"  {i+1}. TEXT: '{link['text']}'")
                logger.info(f"      URL: {link['href']}")
                logger.info(f"      CLASSES: {link['classes']}")
                if link['data_auto_id']:
                    logger.info(f"      DATA-AUTO-ID: {link['data_auto_id']}")
                if link['data_di_id']:
                    logger.info(f"      DATA-DI-ID: {link['data_di_id']}")
                logger.info("")
            
            if len(dept_links) > 10:
                logger.info(f"... and {len(dept_links) - 10} more department links")
                
        except Exception as e:
            logger.error(f"Error analyzing links: {str(e)}")
        
        # Look for specific patterns from your HTML examples
        logger.info("SEARCHING FOR SPECIFIC PATTERNS:")
        
        patterns_to_check = [
            ("produce-taxo-btn", "a.produce-taxo-btn"),
            ("taxonomy-explore__item", "a.taxonomy-explore__item"),
            ("taxonomy-explore__list", "ul.taxonomy-explore__list a"),
            ("linkTaxonomyExplore", "a[data-auto-id='linkTaxonomyExplore']"),
            ("asda-btn--light", "a.asda-btn--light"),
            ("taxonomy-explore__title", "h2.taxonomy-explore__title"),
            ("explore departments", "h2:contains('Explore departments')"),
            ("data-di-id", "a[data-di-id]"),
        ]
        
        for pattern_name, selector in patterns_to_check:
            try:
                if ':contains(' in selector:
                    # Convert to XPath for contains
                    xpath = f"//h2[contains(text(), 'Explore departments')]"
                    elements = self.driver.find_elements(By.XPATH, xpath)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                count = len(elements)
                logger.info(f"Pattern '{pattern_name}': {count} elements found")
                
                if count > 0 and count <= 5:  # Show details for small numbers
                    for i, elem in enumerate(elements):
                        try:
                            text = elem.text.strip()
                            href = elem.get_attribute('href')
                            logger.info(f"  {i+1}. '{text}' -> {href}")
                        except Exception:
                            pass
                            
            except Exception as e:
                logger.error(f"Error checking pattern '{pattern_name}': {str(e)}")
        
        # Check page source for specific text patterns
        logger.info("CHECKING PAGE SOURCE FOR KEY PATTERNS:")
        try:
            page_source = self.driver.page_source.lower()
            
            key_patterns = [
                'explore departments',
                'taxonomy-explore',
                'produce-taxo',
                'data-auto-id="linktaxonomyexplore"',
                'class="asda-btn asda-btn--light'
            ]
            
            for pattern in key_patterns:
                if pattern in page_source:
                    logger.info(f"✓ Found pattern in source: '{pattern}'")
                else:
                    logger.info(f"✗ Pattern NOT found: '{pattern}'")
                    
        except Exception as e:
            logger.error(f"Error checking page source: {str(e)}")
        
        logger.info("="*60)
        logger.info("END DEBUG INSPECTION")
        logger.info("="*60)
        
    def test_specific_selectors(self) -> List[Dict[str, str]]:
        """
        Test specific selectors to see what they find on the current page.
        
        Returns:
            List of found links with metadata
        """
        logger.info("TESTING SPECIFIC SELECTORS:")
        
        # Test the exact selectors from your HTML examples
        test_selectors = [
            "a.produce-taxo-btn",
            "a[class*='produce-taxo-btn']",
            "a.taxonomy-explore__item",
            "a[data-auto-id='linkTaxonomyExplore']",
            "ul.taxonomy-explore__list a",
            "h2.taxonomy-explore__title + ul a",
            ".taxonomy-explore__list a",
            "a.asda-btn.asda-btn--light.taxonomy-explore__item",
            "a[data-di-id]",
            "a[href*='/dept/'][data-di-id]"
        ]
        
        found_links = []
        
        for selector in test_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                count = len(elements)
                
                logger.info(f"Selector '{selector}': {count} elements")
                
                for element in elements:
                    try:
                        href = element.get_attribute('href')
                        text = element.text.strip()
                        
                        if href and text:
                            found_links.append({
                                'selector': selector,
                                'text': text,
                                'url': href,
                                'type': 'test_result'
                            })
                            logger.info(f"  -> Found: '{text}' | {href}")
                    except Exception:
                        continue
                        
            except Exception as e:
                logger.error(f"Error testing selector '{selector}': {str(e)}")
        
        return found_links