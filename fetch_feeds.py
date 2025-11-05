import feedparser
import yaml
import os
from datetime import datetime
from pathlib import Path
import hashlib
import re
from urllib.parse import urlparse, urljoin
import json
import requests
from bs4 import BeautifulSoup
import time

class RSSFeedProcessor:
    def __init__(self, feeds_file='feeds_to_check.txt', posts_dir='_posts', tracking_file='processed_stories.json'):
        self.feeds_file = feeds_file
        self.posts_dir = posts_dir
        self.tracking_file = tracking_file
        self.processed_stories = self.load_processed_stories()
        
    def load_processed_stories(self):
        """Load the set of already processed story URLs/IDs"""
        if os.path.exists(self.tracking_file):
            with open(self.tracking_file, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        return set()
    
    def save_processed_stories(self):
        """Save the set of processed story URLs/IDs"""
        with open(self.tracking_file, 'w', encoding='utf-8') as f:
            json.dump(list(self.processed_stories), f, indent=2)
    
    def get_feed_name(self, feed_url):
        """Extract a clean feed name from the URL"""
        parsed = urlparse(feed_url)
        domain = parsed.netloc.replace('www.', '')
        # Clean up the domain name
        name = domain.split('.')[0]
        return name.title()
    
    def get_story_id(self, entry):
        """Generate a unique ID for a story"""
        # Use link or id if available, otherwise hash the title
        story_id = entry.get('id') or entry.get('link') or entry.get('title')
        return hashlib.md5(story_id.encode('utf-8')).hexdigest()
    
    def clean_html(self, text):
        """Remove HTML tags and clean up text"""
        if not text:
            return ""
        # Remove HTML tags
        clean = re.sub('<.*?>', '', text)
        # Clean up whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean
    
    def get_image_from_entry(self, entry):
        """Extract image URL from RSS entry"""
        # Try various common image fields
        if 'media_content' in entry:
            for media in entry.media_content:
                if media.get('medium') == 'image' or 'image' in media.get('type', ''):
                    return media.get('url')
        
        if 'media_thumbnail' in entry and entry.media_thumbnail:
            return entry.media_thumbnail[0].get('url')
        
        if 'enclosures' in entry:
            for enclosure in entry.enclosures:
                if 'image' in enclosure.get('type', ''):
                    return enclosure.get('href')
        
        # Try to find image in content
        content = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
        if img_match:
            return img_match.group(1)
        
        return None
    
    def fetch_image_from_page(self, url):
        """Fetch the main image from a webpage"""
        if not url:
            return None
        
        try:
            print(f"    Fetching page for image: {url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0'
            }
            
            # Create a session to maintain cookies
            session = requests.Session()
            session.headers.update(headers)
            
            response = session.get(url, timeout=15, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try Open Graph image first
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                image_url = og_image['content']
                # Make absolute URL if relative
                return urljoin(url, image_url)
            
            # Try Twitter Card image
            twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                image_url = twitter_image['content']
                return urljoin(url, image_url)
            
            # Try to find the first large image in the article
            # Look for common article content containers
            article = soup.find(['article', 'main']) or soup
            
            # Find images, prioritizing larger ones
            images = article.find_all('img')
            for img in images:
                src = img.get('src') or img.get('data-src')
                if src:
                    # Skip small images (icons, buttons, etc.)
                    width = img.get('width')
                    height = img.get('height')
                    
                    # Skip if dimensions are known to be small
                    if width and height:
                        try:
                            if int(width) < 200 or int(height) < 200:
                                continue
                        except (ValueError, TypeError):
                            pass
                    
                    # Skip common icon/logo patterns
                    if any(x in src.lower() for x in ['icon', 'logo', 'avatar', 'button', 'sprite']):
                        continue
                    
                    # Return first suitable image
                    return urljoin(url, src)
            
            print(f"    ✗ No suitable image found on page")
            return None
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"    ⚠ Page blocked automated access (403 Forbidden) - skipping image fetch")
            else:
                print(f"    ✗ HTTP Error fetching page: {e}")
            return None
        except requests.RequestException as e:
            print(f"    ✗ Error fetching page: {e}")
            return None
        except Exception as e:
            print(f"    ✗ Error parsing page: {e}")
            return None
    
    def sanitize_filename(self, text):
        """Create a safe filename from text"""
        # Remove special characters and replace spaces with hyphens
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text.lower()[:100]  # Limit length
    
    def get_summary(self, entry, max_words=50):
        """Extract and clean summary text"""
        summary = entry.get('summary', '') or entry.get('description', '')
        summary = self.clean_html(summary)
        
        # Truncate to max_words
        words = summary.split()
        if len(words) > max_words:
            summary = ' '.join(words[:max_words]) + '...'
        
        return summary
    
    def create_post(self, entry, feed_url, feed_name):
        """Create a Jekyll post from an RSS entry"""
        story_id = self.get_story_id(entry)
        
        # Check if already processed
        if story_id in self.processed_stories:
            print(f"  Skipping already processed: {entry.get('title', 'Untitled')}")
            return False
        
        # Extract data
        title = entry.get('title', 'Untitled Story')
        link = entry.get('link', '')
        
        # Get published date
        pub_date = entry.get('published_parsed') or entry.get('updated_parsed')
        if pub_date:
            date = datetime(*pub_date[:6])
        else:
            date = datetime.now()
        
        # Get image
        image = self.get_image_from_entry(entry)
        
        # If no image found in RSS, try fetching from the page
        if not image and link:
            image = self.fetch_image_from_page(link)
            # Small delay to be respectful to the server
            if image:
                time.sleep(0.5)
        
        # Get summary
        summary = self.get_summary(entry)
        
        # Get content
        content = ''
        if 'content' in entry:
            content = entry.content[0].get('value', '')
        elif 'summary' in entry:
            content = entry.summary
        
        content = self.clean_html(content)
        
        # Create filename
        date_str = date.strftime('%Y-%m-%d')
        title_slug = self.sanitize_filename(title)
        filename = f"{date_str}-{title_slug}.md"
        filepath = os.path.join(self.posts_dir, filename)
        
        # Prepare front matter
        front_matter = {
            'layout': 'story',
            'title': title,
            'date': date.strftime('%Y-%m-%d %H:%M:%S -0000'),
            'source_url': link,
            'source_name': feed_name,
            'source_feed': feed_url,
        }
        
        if image:
            front_matter['image'] = image
        
        if summary:
            front_matter['summary'] = summary
        
        # Create post file
        os.makedirs(self.posts_dir, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('---\n')
            f.write(yaml.dump(front_matter, default_flow_style=False, allow_unicode=True))
            f.write('---\n\n')
            f.write(content)
        
        # Mark as processed
        self.processed_stories.add(story_id)
        print(f"  ✓ Created: {filename}")
        return True
    
    def process_feed(self, feed_url):
        """Process a single RSS feed"""
        print(f"\nProcessing: {feed_url}")
        
        try:
            feed = feedparser.parse(feed_url)
            
            if feed.bozo and not feed.entries:
                print(f"  ✗ Error parsing feed: {feed.bozo_exception}")
                return 0
            
            feed_name = self.get_feed_name(feed_url)
            
            # If feed has a title, use that instead
            if hasattr(feed, 'feed') and hasattr(feed.feed, 'title'):
                feed_name = feed.feed.title
            
            new_stories = 0
            for entry in feed.entries:
                if self.create_post(entry, feed_url, feed_name):
                    new_stories += 1
            
            print(f"  Found {new_stories} new stories")
            return new_stories
            
        except Exception as e:
            print(f"  ✗ Error proce