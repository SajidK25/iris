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
    print("ERROR: PINECONE_API_KEY not found in environment variables")
    raise ValueError("PINECONE_API_KEY not found in environment variables")
print("DEBUG: Initializing Pinecone with API key")
pc = Pinecone(api_key=PINECONE_API_KEY)
image_index = pc.Index("apartment-images-search")
print("DEBUG: Connected to Pinecone image_index")

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
print("DEBUG: Loaded SentenceTransformer model")
INDEX_NAME = "apartments-search"
APARTMENTS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "apartments.json"
)
print(f"DEBUG: APARTMENTS_FILE path: {APARTMENTS_FILE}")

def create_embedding(text):
    print(f"DEBUG: Creating embedding for text: {text[:50]}...")
    try:
        embedding = model.encode(text)
        return embedding.tolist()
    except Exception as e:
        print(f"ERROR: Error creating embedding: {e}")
        return None


@lru_cache(maxsize=128)
def _get_query_embedding(query: str):
    print(f"DEBUG: Getting cached query embedding for: {query}")
    return create_embedding(query)


def search_apartments(query, filter_dict=None, top_k=10, image_urls=None, page=1):
    print(f"DEBUG: search_apartments called with query: {query}, top_k: {top_k}, page: {page}, image_urls: {image_urls}")
    try:
        index = pc.Index(INDEX_NAME)
        print(f"DEBUG: Connected to Pinecone index: {INDEX_NAME}")
        search_text = query.strip()
        query_embedding = None

        if image_urls and len(image_urls) > 0:
            print(f"DEBUG: Processing {len(image_urls)} image URLs")
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                print("ERROR: OPENAI_API_KEY not found in environment")
                return []
            
            try:
                client = openai.OpenAI(api_key=openai_api_key)
                print("DEBUG: Initialized OpenAI client")
                messages = [
                    {"role": "system", "content": "You are a helpful assistant that generates semantic search descriptions for apartment listings. Provide a concise description (less than 20 words) focusing on aesthetics and design elements visible in the images."}
                ]
                content = []
                if search_text:
                    content.append(
                        {"type": "text", 
                         "text": f"Generate a 20-word search description combining these images with the text query: '{search_text}'."}
                    )
                else:
                    content.append(
                        {"type": "text", 
                         "text": "Generate a 20-word search description for these apartment images, focusing on aesthetics and design."}
                    )
                for url in image_urls[:5]:
                    print(f"DEBUG: Adding image URL: {url[:60]}...")
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
                print(f"DEBUG: Combined query from OpenAI: {combined_query}")
                query_embedding = create_embedding(combined_query)
            except Exception as api_error:
                print(f"ERROR: OpenAI API error: {api_error}")
                if search_text:
                    print(f"DEBUG: Falling back to text-only query: {search_text}")
                    query_embedding = create_embedding(search_text)
                else:
                    print("ERROR: No fallback query available")
                    return []
        else:
            query_embedding = create_embedding(search_text)
            print("DEBUG: Created text-only embedding")

        if query_embedding is None:
            print("ERROR: Failed to create embedding for query")
            return []

        print(f"DEBUG: Querying Pinecone with top_k: {top_k}, page: {page}, filter_dict: {filter_dict}")
        # Note: Pinecone doesn't support offset natively; simulate pagination
        search_results = index.query(
            vector=query_embedding,
            filter=filter_dict,
            top_k=top_k * page,  # Fetch more results to simulate pagination
            include_metadata=True
        )
        print(f"DEBUG: Pinecone query returned {len(search_results.matches)} matches")

        # Simulate pagination by slicing results
        start_idx = (page - 1) * top_k
        end_idx = start_idx + top_k
        matches = search_results.matches[start_idx:end_idx]

        formatted_results = []
        for match in matches:
            result = {"id": match.id, "score": match.score, "metadata": match.metadata}
            formatted_results.append(result)

        print(f"DEBUG: Returning {len(formatted_results)} formatted results")
        return formatted_results
    except Exception as e:
        print(f"ERROR: search_apartments failed: {e}")
        print(traceback.format_exc())
        return []


def get_apartment_preview_by_id(apartment_id, query=None):
    print(f"DEBUG: get_apartment_preview_by_id called with apartment_id: {apartment_id}, query: {query}")
    try:
        print(f"DEBUG: Reading apartments.json from: {APARTMENTS_FILE}")
        with open(APARTMENTS_FILE, "r") as f:
            apartments = json.load(f)
        for apartment in apartments:
            if apartment.get("id") == apartment_id:
                photos = apartment.get("photos", [])
                if query and photos and len(photos) > 0:
                    print(f"DEBUG: Ranking photos for query: {query}")
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
                print(f"DEBUG: Returning apartment preview: {preview['id']}")
                return preview
        print(f"DEBUG: Apartment not found: {apartment_id}")
        return None
    except Exception as e:
        print(f"ERROR: get_apartment_preview_by_id failed: {e}")
        print(traceback.format_exc())
        return None


def rank_apartment_images_by_query(apartment_id, query, original_photos):
    print(f"DEBUG: rank_apartment_images_by_query called with apartment_id: {apartment_id}, query: {query}")
    try:
        photo_urls = [
            photo["url"] if isinstance(photo, dict) and "url" in photo
            else photo if isinstance(photo, str)
            else None
            for photo in original_photos
        ]
        photo_urls = [u for u in photo_urls if u]
        if not photo_urls:
            print("DEBUG: No valid photo URLs found")
            return original_photos

        query_emb = _get_query_embedding(query)
        if not query_emb:
            print("ERROR: Failed to create query embedding")
            return photo_urls

        print(f"DEBUG: Querying Pinecone image_index for apartment_id: {apartment_id}")
        results = image_index.query(
            vector=query_emb,
            filter={"apartment_id": apartment_id},
            top_k=len(photo_urls),
            include_metadata=True
        )
        print(f"DEBUG: Pinecone image query returned {len(results.matches)} matches")

        url_score_map = {
            m.metadata["original_url"]: m.score
            for m in (results.matches or [])
            if m.metadata.get("original_url")
        }

        sorted_urls = sorted(
            photo_urls,
            key=lambda u: url_score_map.get(u, -1),
            reverse=True
        )
        print(f"DEBUG: Returning {len(sorted_urls)} sorted photo URLs")
        return sorted_urls
    except Exception as e:
        print(f"ERROR: rank_apartment_images_by_query failed: {e}")
        print(traceback.format_exc())
        return [p["url"] if isinstance(p, dict) and "url" in p else p for p in original_photos]


def get_apartment_details_by_id(apartment_id, query=None):
    print(f"DEBUG: get_apartment_details_by_id called with apartment_id: {apartment_id}, query: {query}")
    try:
        print(f"DEBUG: Reading apartments.json from: {APARTMENTS_FILE}")
        with open(APARTMENTS_FILE, "r") as f:
            apartments = json.load(f)

        for apartment in apartments:
            if apartment.get("id") == apartment_id:
                result = apartment.copy()
                photos = apartment.get("photos", [])
                if query and photos and len(photos) > 0:
                    print(f"DEBUG: Ranking photos for query: {query}")
                    ranked_photos = rank_apartment_images_by_query(apartment_id, query, photos)
                    if ranked_photos:
                        if ranked_photos and isinstance(ranked_photos[0], dict) and "url" in ranked_photos[0]:
                            result["photos"] = [p["url"] for p in ranked_photos if isinstance(p, dict) and "url" in p]
                        else:
                            result["photos"] = ranked_photos
                
                print(f"DEBUG: Returning apartment details: {result['id']}")
                return result

        print(f"DEBUG: Apartment not found: {apartment_id}")
        return None
    except Exception as e:
        print(f"ERROR: get_apartment_details_by_id failed: {e}")
        print(traceback.format_exc())
        return None