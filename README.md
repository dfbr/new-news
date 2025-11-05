# New News

A news aggregation website built with Jekyll and hosted on GitHub Pages.

## Features

- Light blue themed design
- Responsive story cards with images and summaries
- Dynamic front page showing stories based on feed count
- "More Stories" page for overflow content
- Individual story pages with featured images and source links
- No footer clutter

## Local Development

1. Install Ruby and Bundler
2. Install dependencies:
   ```bash
   bundle install
   ```
3. Run the local server:
   ```bash
   bundle exec jekyll serve
   ```
4. Visit `http://localhost:4000` in your browser

## Project Structure

- `_config.yml` - Site configuration
- `_layouts/` - Page templates (default, story)
- `_posts/` - Story content (markdown files)
- `assets/css/` - Stylesheets
- `index.html` - Home page
- `more-stories.html` - Additional stories page
- `feeds_to_check.txt` - List of RSS feeds (determines max stories on front page)

## Adding Stories

### Automatic (via RSS feeds)

Stories are automatically fetched daily from the RSS feeds listed in `feeds_to_check.txt` via GitHub Actions workflow.

### Manual

Create markdown files in `_posts/` with this format:

```markdown
---
layout: story
title: "Story Title"
date: 2025-11-05 10:00:00 -0000
image: "path/to/image.jpg"
summary: "Brief summary"
source_url: "https://source.com"
source_name: "Source Name"
source_feed: "https://source.com/feed/"
---

Story content here...
```

### Fetch Stories Manually

To manually fetch stories from RSS feeds:

```bash
pip install -r requirements.txt
python fetch_feeds.py
```

## Deployment

This site is designed to be deployed on GitHub Pages with an automated workflow to update content weekly from the RSS feeds in `feeds_to_check.txt`.

## Maximum Stories on Front Page

The number of stories displayed on the front page equals the number of lines in `feeds_to_check.txt` (currently 10 feeds).
