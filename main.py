

import os
import asyncio
import uuid
from datetime import datetime
from pathlib import Path
import random
import time

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from playwright.async_api import async_playwright

# --- Configuration ---
# Directory for storing generated files. This should be a persistent volume in Coolify.
OUTPUT_DIR = Path("/app/output") # This will be mounted to a persistent volume in Coolify
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- FastAPI App Setup ---
app = FastAPI()

# Mount static files (if any, though for this simple UI, it's not strictly needed yet)
# app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates for serving HTML
templates = Jinja2Templates(directory="templates")

# --- Data Models ---
class ScrapeRequest(BaseModel):
    query: str

# --- Global State (for simplicity, in a real app, use a database) ---
# This will store ongoing and completed scrape jobs.
# In a production environment, this should be persisted (e.g., in a database)
# as the app might restart. For this simple use case, in-memory is fine.
scrape_jobs = {} # {job_id: {"status": "running/completed/failed", "file": "filename.txt"}}
stop_signals = {} # {job_id: True/False}

# --- Helper Functions ---
async def get_youtube_channel_urls(job_id: str, query: str, num_channels: int = 1000):
    urls = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()

        print("Launching browser...")
        try:
            if query == "random":
                # For random, we'll just browse YouTube's homepage or trending
                print("Navigating to YouTube homepage for random channels...")
                await page.goto("https://www.youtube.com/", wait_until="networkidle", timeout=90000) # Increased timeout
                await asyncio.sleep(5) # Initial wait for dynamic content
                print("Page loaded. Attempting to scroll and find channels.")
                
                # Scroll down multiple times to load more content and find diverse channels
                for i in range(10): # Increased scrolls
                    print(f"Scrolling down (random) - iteration {i+1}...")
                    await page.keyboard.press('End') # Simulate pressing End key for scrolling
                    await asyncio.sleep(random.uniform(2, 4)) # Random delay
                    
                    # Try to find channel links on the homepage/trending
                    await page.wait_for_selector("ytd-channel-renderer, ytd-grid-channel-renderer, ytd-video-renderer", timeout=10000) # Wait for channel elements to appear
                    channel_elements = await page.query_selector_all("ytd-channel-renderer a[href*=\"/channel/\"], ytd-channel-renderer a[href*=\"/@\"]")
                    if not channel_elements:
                        # Fallback for video results that might contain channel links
                        channel_elements = await page.query_selector_all("ytd-video-renderer a[href*=\"/channel/\"], ytd-video-renderer a[href*=\"/@\"]")
                    print(f"Found {len(channel_elements)} potential channel elements on random page.")
                    for element in channel_elements:
                        href = await element.get_attribute("href")
                        print(f"  - Found potential href: {href}") # Added for debugging
                        if href and ("/channel/" in href or "/@" in href):
                            full_url = "https://www.youtube.com" + href.split("?")[0]
                            if full_url not in urls:
                                urls.add(full_url)
                                print(f"Added random channel: {full_url}. Total: {len(urls)}")
                                if len(urls) >= num_channels:
                                    break
                    if len(urls) >= num_channels:
                        break
                print(f"Finished random channel collection attempt. Total unique channels: {len(urls)}")

            else:
                search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}&sp=EgIQAg%253D%253D" # Filter for channels
                print(f"Navigating to search results: {search_url}")
                await page.goto(search_url, wait_until="networkidle", timeout=90000) # Increased timeout
                await asyncio.sleep(5) # Initial wait for dynamic content
                print("Search results page loaded.")

                # Scroll down to load more channels
                while len(urls) < num_channels:
                    print(f"Collected {len(urls)} channels. Scrolling for more...")
                    old_urls_count = len(urls)
                    await page.keyboard.press('End') # Simulate pressing End key for scrolling
                    await asyncio.sleep(random.uniform(3, 5)) # Random delay after scroll

                    # Wait for new content to load by checking if the number of URLs increases
                    start_time = time.time()
                    while len(urls) == old_urls_count and (time.time() - start_time) < 15: # Wait up to 15 seconds for new URLs
                        await page.wait_for_selector("ytd-channel-renderer, ytd-grid-channel-renderer, ytd-video-renderer", timeout=10000) # Wait for channel elements to appear
                        channel_elements = await page.query_selector_all("ytd-channel-renderer a[href*=\"/channel/\"], ytd-channel-renderer a[href*=\"/@\"]")
                        if not channel_elements:
                            channel_elements = await page.query_selector_all("ytd-video-renderer a[href*=\"/channel/\"], ytd-video-renderer a[href*=\"/@\"]")
                        
                        for element in channel_elements:
                            href = await element.get_attribute("href")
                            if href and ("/channel/" in href or "/@" in href):
                                full_url = "https://www.youtube.com" + href.split("?")[0]
                                if full_url not in urls:
                                    urls.add(full_url)
                                    print(f"Added search channel: {full_url}. Total: {len(urls)}")
                        
                        if len(urls) == old_urls_count:
                            await asyncio.sleep(1) # Wait a bit before re-checking
                        else:
                            print(f"New URLs found after scrolling. Total: {len(urls)}")
                            break # New URLs found, break inner loop
                    
                    if len(urls) == old_urls_count: # If no new URLs after waiting, we might have hit the end
                        print("No new URLs found after scrolling and waiting. Assuming end of results.")
                        break

                    # Scroll to the bottom of the page
                    print("Scrolling to bottom of page...")
                    await page.evaluate("window.scrollBy(0, document.body.scrollHeight);")
                    await asyncio.sleep(3) # Wait for new content to load

                    # Check if we hit the end of results (e.g., "No more results")
                    no_results = await page.query_selector("yt-formatted-string#message-text")
                    if no_results:
                        text_content = await no_results.inner_text()
                        if "No more results" in text_content or "No results found" in text_content:
                            print("Reached end of search results or no more results found.")
                            break
                    
                    # Add a safeguard to prevent infinite loops if no new content loads
                    if len(channel_elements) == 0 and len(urls) == 0:
                        print("No channel elements found and no URLs collected. Breaking to prevent infinite loop.")
                        break

                print(f"Finished search channel collection attempt. Total unique channels: {len(urls)}")

        except Exception as e:
            print(f"An error occurred during scraping: {e}")
        finally:
            print("Closing browser.")
            await browser.close()
    return list(urls)[:num_channels] # Ensure we return exactly num_channels or fewer if not found

async def perform_scrape_task(job_id: str, query: str):
    try:
        print(f"Starting scrape job {job_id} for query: '{query}'")
        scrape_jobs[job_id]["status"] = "running"
        
        channel_urls = await get_youtube_channel_urls(job_id, query) # Pass job_id to get_youtube_channel_urls
        
        if not channel_urls:
            scrape_jobs[job_id]["status"] = "failed"
            print(f"Scrape job {job_id} failed: No channels found.")
            return

        # Generate filename
        timestamp = int(datetime.now().timestamp())
        safe_query = query.replace(" ", "_").replace("/", "_").replace("\\", "_")
        filename = f"{timestamp}_{safe_query}.txt" if query != "random" else f"{timestamp}_random.txt"
        file_path = OUTPUT_DIR / filename

        with open(file_path, "w") as f:
            for i, url in enumerate(channel_urls):
                f.write(f"{i+1}. {url}\n")
        
        scrape_jobs[job_id]["status"] = "completed"
        scrape_jobs[job_id]["file"] = filename
        print(f"Scrape job {job_id} completed. File saved to {file_path}")

    except Exception as e:
        scrape_jobs[job_id]["status"] = "failed"
        print(f"Scrape job {job_id} failed due to an exception: {e}")
    finally:
        # Clean up stop signal after job is done or failed
        if job_id in stop_signals:
            del stop_signals[job_id]

# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/scrape")
async def start_scrape(scrape_request: ScrapeRequest, background_tasks: BackgroundTasks):
    print(f"Received scrape request for query: {scrape_request.query}")
    job_id = str(uuid.uuid4())
    scrape_jobs[job_id] = {"status": "queued", "query": scrape_request.query}
    background_tasks.add_task(perform_scrape_task, job_id, scrape_request.query)
    print(f"Queued scrape job {job_id} for query: {scrape_request.query}")
    return {"message": f"Scraping job started for '{scrape_request.query}'. Job ID: {job_id}", "job_id": job_id}

@app.post("/upload-and-scrape")
async def upload_and_scrape(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    print(f"Received file upload for scraping. File: {file.filename}")
    content = await file.read()
    search_terms = content.decode("utf-8").splitlines()
    search_terms = [term.strip() for term in search_terms if term.strip()]

    if not search_terms:
        raise HTTPException(status_code=400, detail="File is empty or contains no valid search terms.")

    print(f"Processing {len(search_terms)} search terms from file.")
    for term in search_terms:
        job_id = str(uuid.uuid4())
        scrape_jobs[job_id] = {"status": "queued", "query": term}
        background_tasks.add_task(perform_scrape_task, job_id, term)
        print(f"Queued scrape job {job_id} for term: {term}")
    
    return {"message": f"Queued {len(search_terms)} scraping jobs from file.", "job_ids": list(scrape_jobs.keys())}

@app.post("/stop-scrape")
async def stop_scrape_request():
    # This will signal all currently running jobs to stop. 
    # In a more complex app, you might want to stop a specific job_id.
    for job_id in scrape_jobs:
        if scrape_jobs[job_id]["status"] == "running":
            stop_signals[job_id] = True
            print(f"Stop signal sent for job {job_id}")
    return {"message": "Stop signal sent to all running scrape jobs."}

@app.get("/files")
async def list_files():
    # List files in the output directory
    files = [f.name for f in OUTPUT_DIR.iterdir() if f.is_file()]
    return files

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(path=file_path, filename=filename, media_type="text/plain")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


