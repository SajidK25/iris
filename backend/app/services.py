import os
import openai    
import json
import time
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
if not PINECONE_API_KEY:
    raise ValueError("PINECONE_API_KEY not found in environment variables")
pc = Pinecone(api_key=PINECONE_API_KEY)
image_index = pc.Index("apartment-images-search")

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
INDEX_NAME = "apartments-search"
APARTMENTS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "apartments.json"
)

def create_embedding(text):
    """Create an embedding for the given text using sentence-transformers"""
    try:
        embedding = model.encode(text)
        return embedding.tolist()
    except Exception as e:
        print(f"Error creating embedding: {e}")
        return None


@lru_cache(maxsize=128)
def _get_query_embedding(query: str):
    return create_embedding(query)


def search_apartments(query, filter_dict=None, top_k=10, image_urls=None):
    """
    Search for apartments in the Pinecone index

    Args:
        query (str): The search query
        filter_dict (dict, optional): Filter criteria for metadata. Defaults to None.
        top_k (int, optional): Number of results to return. Defaults to 10.
        image_urls (list, optional): List of image URLs to analyze. Defaults to None.

    Returns:
        list: List of matching apartments with scores
    """
    index = pc.Index(INDEX_NAME)
    search_text = query.strip()
    if image_urls and len(image_urls) > 0:
        try:
            print(f"Processing {len(image_urls)} image URLs for analysis")
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                print("ERROR: OPENAI_API_KEY not found in environment")
                return []
            
            try:
                client = openai.OpenAI(api_key=openai_api_key)
                print("Successfully initialized OpenAI client")
                messages = [
                    {"role": "system", "content": "You are a helpful assistant that generates semantic search descriptions for apartment listings. Provide a concise description (less than 20 words) focusing on aesthetics and design elements visible in the images."}
                ]
                content = []
                if search_text:
                    content.append(
                        {"type": "text", 
                         "text": f"These are images of apartment interiors/exteriors. Generate a 20-word search description that combines analyzing these images with the text query: '{search_text}'. Focus on aesthetics and design elements."}
                    )
                else:
                    content.append(
                        {"type": "text", 
                         "text": "These are images of apartment interiors/exteriors. Generate a 20-word search description focusing on aesthetics and design elements visible in the images."}
                    )
                for url in image_urls[:5]:
                    print(f"Adding image URL to content: {url[:60]}...")
                    content.append(
                        {"type": "image_url", "image_url": {"url": url}}
                    )
                messages.append({"role": "user", "content": content})
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    max_tokens=100
                )
                combined_query = response.choices[0].message.content.strip()
                print(f"Combined query for embedding: {combined_query}")
                query_embedding = create_embedding(combined_query)
                
            except Exception as api_error:
                print(f"ERROR during OpenAI API call: {api_error}")
                if search_text:
                    print(f"Falling back to text-only query: {search_text}")
                    query_embedding = create_embedding(search_text)
                else:
                    print("No fallback query available")
                    return []
        except Exception as e:
            print(f"Error analyzing images with OpenAI: {e}")
            if search_text:
                query_embedding = create_embedding(search_text)
            else:
                print("No fallback query available")
                return []
    else:
        query_embedding = create_embedding(search_text)

    if query_embedding is None:
        print("Failed to create embedding for query")
        return []
    search_results = index.query(
        vector=query_embedding, filter=filter_dict, top_k=top_k, include_metadata=True
    )
    formatted_results = []
    for match in search_results.matches:
        result = {"id": match.id, "score": match.score, "metadata": match.metadata}
        formatted_results.append(result)

    return formatted_results


def get_apartment_preview_by_id(apartment_id, query=None):
    """
    Get preview data for a specific apartment by ID, with optional query parameter
    to order images by relevance to the query

    Args:
        apartment_id (str): The ID of the apartment
        query (str, optional): The search query to rank images by. Default is None.

    Returns:
        dict: Preview data for the apartment or None if not found
    """
    try:
        with open(APARTMENTS_FILE, "r") as f:
            apartments = json.load(f)
        for apartment in apartments:
            if apartment.get("id") == apartment_id:
                photos = apartment.get("photos", [])
                if query and photos and len(photos) > 0:
                    ranked_photos = rank_apartment_images_by_query(apartment_id, query, photos)
                    if ranked_photos:
                        photos = ranked_photos

                final_photos = photos
                if photos and len(photos) > 0:
                    if isinstance(photos[0], dict) and "url" in photos[0]:
                        final_photos = [p["url"] for p in photos if isinstance(p, dict) and "url" in p]
                        
                preview = {
                    "id": apartment.get("id"),
                    "propertyName": apartment.get("propertyName"),
                    "location": {
                        "city": apartment.get("location", {}).get("city"),
                        "state": apartment.get("location", {}).get("state"),
                    },
                    "coordinates": apartment.get(
                        "coordinates",
                        {
                            "latitude": 34.0522,
                            "longitude": -118.2437,
                        },
                    ),
                    "rent": apartment.get("rent"),
                    "beds": apartment.get("beds"),
                    "baths": apartment.get("baths"),
                    "sqft": apartment.get("sqft"),
                    "photos": final_photos if final_photos and len(final_photos) > 0 else None,
                }
                return preview
        return None
    except Exception as e:
        print(f"Error retrieving apartment preview: {e}")
        return None


def rank_apartment_images_by_query(apartment_id, query, original_photos):
    """
    Rank apartment images by relevance to a search query using Pinecone

    Args:
        apartment_id (str): The ID of the apartment
        query (str): The search query to rank images by
        original_photos (list): Original list of photo objects or URLs

    Returns:
        list: Reordered list of URLs (strings), most relevant first
    """
    try:
        # 1. Extract URLs quickly
        photo_urls = [
            photo["url"] if isinstance(photo, dict) and "url" in photo
            else photo if isinstance(photo, str)
            else None
            for photo in original_photos
        ]
        photo_urls = [u for u in photo_urls if u]
        if not photo_urls:
            return original_photos

        # 2. Embed the query (cached)
        query_emb = _get_query_embedding(query)
        if not query_emb:
            return photo_urls

        # 3. Only request exactly as many neighbors as you have photos
        results = image_index.query(
            vector=query_emb,
            filter={"apartment_id": apartment_id},
            top_k=len(photo_urls),
            include_metadata=True
        )

        # 4. Build URL→score map in one go
        url_score_map = {
            m.metadata["original_url"]: m.score
            for m in (results.matches or [])
            if m.metadata.get("original_url")
        }

        # 5. Sort using Python’s built‑in
        return sorted(
            photo_urls,
            key=lambda u: url_score_map.get(u, -1),
            reverse=True
        )
    except Exception as e:
        print(f"Error ranking apartment images: {e}")
        import traceback
        print(traceback.format_exc())
        # Return the extracted URLs if available, otherwise original photos
        return [p["url"] if isinstance(p, dict) and "url" in p else p for p in original_photos]


def get_apartment_details_by_id(apartment_id, query=None):
    """
    Get all details for a specific apartment by ID, with optional query parameter
    to order images by relevance to the query

    Args:
        apartment_id (str): The ID of the apartment
        query (str, optional): The search query to rank images by. Default is None.

    Returns:
        dict: All data for the apartment or None if not found
    """
    try:
        with open(APARTMENTS_FILE, "r") as f:
            apartments = json.load(f)

        # Find the apartment with the matching ID
        for apartment in apartments:
            if apartment.get("id") == apartment_id:
                # Make a deep copy to avoid modifying the original data
                result = apartment.copy()
                
                # If we have a query and photos, rank them by relevance
                photos = apartment.get("photos", [])
                if query and photos and len(photos) > 0:
                    ranked_photos = rank_apartment_images_by_query(apartment_id, query, photos)
                    if ranked_photos:
                        # Ensure we're returning a list of string URLs
                        if ranked_photos and isinstance(ranked_photos[0], dict) and "url" in ranked_photos[0]:
                            result["photos"] = [p["url"] for p in ranked_photos if isinstance(p, dict) and "url" in p]
                        else:
                            result["photos"] = ranked_photos
                
                return result

        # If no matching apartment is found
        return None
    except Exception as e:
        print(f"Error retrieving apartment details: {e}")
        return None