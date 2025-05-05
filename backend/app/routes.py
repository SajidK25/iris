from flask import Blueprint, request, jsonify
from app.services import (
    search_apartments,
    get_apartment_preview_by_id,
    get_apartment_details_by_id,
)
import traceback

search_bp = Blueprint("search", __name__)

@search_bp.route("/api/search", methods=["GET"])
def search():
    """
    Search for apartments based on text query, image URLs, and optional filters.
    
    Query Parameters:
        query (str, optional): Text search query to match against apartment descriptions
        imageUrls (str, optional): JSON string containing array of image URLs for visual search
        limit (int, optional): Maximum number of results to return (default: 50)
        
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
    try:
        print(f"DEBUG: Request parameters: {dict(request.args)}")
        query = request.args.get("query", "")

        image_urls_json = request.args.get("imageUrls")
        image_urls = []
        if image_urls_json:
            try:
                import json
                image_urls = json.loads(image_urls_json)
                print(f"DEBUG: Received {len(image_urls)} image URLs")
            except json.JSONDecodeError as e:
                print(f"ERROR: Failed to parse image URLs: {image_urls_json[:100]}..., error: {e}")
            except Exception as e:
                print(f"ERROR: Unexpected error handling image URLs: {e}")
        
        if not query.strip() and not image_urls:
            print("ERROR: No query or image URLs provided")
            return jsonify({"error": "Query parameter or image URLs are required"}), 400

        # Get optional parameters
        top_k = request.args.get("limit", default=50, type=int)

        filter_dict = {}
        min_price = request.args.get("min_price", type=float)
        max_price = request.args.get("max_price", type=float)
        min_bedrooms = request.args.get("min_bedrooms", type=float)
        max_bedrooms = request.args.get("max_bedrooms", type=float)
        min_bathrooms = request.args.get("min_bathrooms", type=float)
        max_bathrooms = request.args.get("max_bathrooms", type=float)
        
        if min_price is not None:
            filter_dict["price_min"] = {
                "$gte": min_price
            }
        if max_price is not None:
            filter_dict["price_max"] = {
                "$lte": max_price
            }
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

        results = search_apartments(query, filter_dict, top_k, image_urls)

        print(f"DEBUG: Search completed, returned {len(results)} results")
        print(f"DEBUG: Results: {results}")

        return jsonify({"results": results})
    except Exception as e:
        error_message = f"Error in search endpoint: {str(e)}"
        print(traceback.format_exc())
        return jsonify({"error": error_message}), 500


@search_bp.route("/api/apartment/preview/<string:apartment_id>", methods=["GET"])
def apartment_preview(apartment_id):
    """
    Get preview data for a specific apartment by ID, with optional query parameter
    to order images by relevance to the query

    Args:
        apartment_id (str): The ID of the apartment to retrieve preview data for

    Query params:
        query (str, optional): The search query to rank images by relevance

    Returns:
        JSON: Preview data for the apartment or error message
    """
    try:
        query = request.args.get("query", "")
        apartment = get_apartment_preview_by_id(apartment_id, query)
        if apartment is None:
            return jsonify({"error": "Apartment not found"}), 404
        return jsonify({"apartment": apartment})
    except Exception as e:
        error_message = f"Error in apartment preview endpoint: {str(e)}"
        print(traceback.format_exc())
        return jsonify({"error": error_message}), 500


@search_bp.route("/api/apartment/details/<string:apartment_id>", methods=["GET"])
def apartment_details(apartment_id):
    """
    Get full details for a specific apartment by ID

    Args:
        apartment_id (str): The ID of the apartment to retrieve details for

    Query params:
        query (str, optional): The search query to rank images by relevance

    Returns:
        JSON: All data for the apartment or error message
    """
    try:
        query = request.args.get("query", "")
        apartment = get_apartment_details_by_id(apartment_id, query)
        if apartment is None:
            return jsonify({"error": "Apartment not found"}), 404

        return jsonify({"apartment": apartment})
    except Exception as e:
        error_message = f"Error in apartment details endpoint: {str(e)}"
        print(traceback.format_exc())
        return jsonify({"error": error_message}), 500