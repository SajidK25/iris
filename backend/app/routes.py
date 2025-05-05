from flask import Blueprint, request, jsonify
from app.services import (
    search_apartments,
    get_apartment_preview_by_id,
    get_apartment_details_by_id,
)
import traceback
from urllib.parse import unquote

search_bp = Blueprint("search", __name__)
print("DEBUG: Initializing search_bp")

@search_bp.route("/api/search", methods=["GET", "OPTIONS"])
def search():
    """
    Search for apartments based on text query, image URLs, and optional filters.
    
    Query Parameters:
        query (str, optional): Text search query to match against apartment descriptions
        imageUrls (str, optional): JSON string containing array of image URLs for visual search
        limit (int, optional): Maximum number of results to return (default: 50)
        page (int, optional): Page number for pagination (not currently used)
        
    Filter Parameters:
        min_price (float, optional): Minimum price filter
        max_price (float, optional): Maximum price filter
        min_bedrooms (float, optional): Minimum number of bedrooms
        max_bedrooms (float, optional): Maximum number of bedrooms
        min_bathrooms (float, optional): Minimum number of bathrooms
        max_bathrooms (float, optional): Maximum number of bathrooms
        
    Returns:
        JSON response containing:
            - results: Array of matching apartment objects
            - error: Error message if something went wrong
            
    Example:
        GET /api/search?query=modern&min_price=1000&max_price=3000&min_bedrooms=2
    """
    print("DEBUG: /api/search endpoint hit, method:", request.method)
    if request.method == "OPTIONS":
        print("DEBUG: Handling OPTIONS request for /api/search")
        return jsonify({}), 200

    try:
        print(f"DEBUG: Request parameters: {dict(request.args)}")
        query = request.args.get("query", "")
        query = unquote(query)  # Decode query (e.g., modern%2520loft -> modern loft)
        print(f"DEBUG: Decoded query: {query}")

        image_urls_json = request.args.get("imageUrls")
        image_urls = []
        if image_urls_json:
            try:
                import json
                image_urls = json.loads(image_urls_json)  # Fixed typo
                print(f"DEBUG: Received {len(image_urls)} image URLs: {image_urls}")
            except json.JSONDecodeError as e:
                print(f"ERROR: Failed to parse image URLs: {image_urls_json[:100]}..., error: {e}")
            except Exception as e:
                print(f"ERROR: Unexpected error handling image URLs: {e}")

        if not query.strip() and not image_urls:
            print("ERROR: No query or image URLs provided")
            return jsonify({"error": "Query parameter or image URLs are required"}), 400

        top_k = request.args.get("limit", default=50, type=int)
        page = request.args.get("page", default=1, type=int)
        print(f"DEBUG: top_k: {top_k}, page: {page}")

        filter_dict = {}
        min_price = request.args.get("min_price", type=float)
        max_price = request.args.get("max_price", type=float)
        min_bedrooms = request.args.get("min_bedrooms", type=float)
        max_bedrooms = request.args.get("max_bedrooms", type=float)
        min_bathrooms = request.args.get("min_bathrooms", type=float)
        max_bathrooms = request.args.get("max_bathrooms", type=float)
        
        if min_price is not None:
            filter_dict["price_min"] = {"$gte": min_price}
        if max_price is not None:
            filter_dict["price_max"] = {"$lte": max_price}
        if min_bedrooms is not None or max_bedrooms is not None:
            filter_dict["bedrooms"] = {
                "$gte": min_bedrooms if min_bedrooms is not None else 0,
                "$lte": max_bedrooms if max_bedrooms is not None else float('9999')
            }
        if min_bathrooms is not None or max_bathrooms is not None:
            filter_dict["bathrooms"] = {
                "$gte": min_bathrooms if min_bathrooms is not None else 0,
                "$lte": max_bathrooms if max_bathrooms is not None else float('9999')
            }
        if not filter_dict:
            filter_dict = None
        print(f"DEBUG: filter_dict: {filter_dict}")

        print("DEBUG: Calling search_apartments")
        results = search_apartments(query, filter_dict, top_k, image_urls, page)
        print(f"DEBUG: Search completed, returned {len(results)} results")
        print(f"DEBUG: Results: {results}")

        return jsonify({"results": results})
    except Exception as e:
        error_message = f"Error in search endpoint: {str(e)}"
        print(f"ERROR: {error_message}")
        print(traceback.format_exc())
        return jsonify({"error": error_message}), 500


@search_bp.route("/api/apartment/preview/<string:apartment_id>", methods=["GET", "OPTIONS"])
def apartment_preview(apartment_id):
    print("DEBUG: /api/apartment/preview endpoint hit")
    if request.method == "OPTIONS":
        print("DEBUG: Handling OPTIONS request for /api/apartment/preview")
        return jsonify({}), 200
    try:
        query = request.args.get("query", "")
        apartment = get_apartment_preview_by_id(apartment_id, query)
        if apartment is None:
            return jsonify({"error": "Apartment not found"}), 404
        return jsonify({"apartment": apartment})
    except Exception as e:
        error_message = f"Error in apartment preview endpoint: {str(e)}"
        print(f"ERROR: {error_message}")
        print(traceback.format_exc())
        return jsonify({"error": error_message}), 500


@search_bp.route("/api/apartment/details/<string:apartment_id>", methods=["GET", "OPTIONS"])
def apartment_details(apartment_id):
    print("DEBUG: /api/apartment/details endpoint hit")
    if request.method == "OPTIONS":
        print("DEBUG: Handling OPTIONS request for /api/apartment/details")
        return jsonify({}), 200
    try:
        query = request.args.get("query", "")
        apartment = get_apartment_details_by_id(apartment_id, query)
        if apartment is None:
            return jsonify({"error": "Apartment not found"}), 404
        return jsonify({"apartment": apartment})
    except Exception as e:
        error_message = f"Error in apartment details endpoint: {str(e)}"
        print(f"ERROR: {error_message}")
        print(traceback.format_exc())
        return jsonify({"error": error_message}), 500