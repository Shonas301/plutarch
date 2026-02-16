# Getting Started


The ArcTracker API provides access to ARC Raiders game data. Public endpoints require no authentication, while user data endpoints use a dual-key authentication system.

1. Public endpoints (items, quests, hideout, projects) are freely accessible with no authentication.

2. To access user data, register an app at the Developer Dashboard to get an app key.

3. Users create personal API keys in their Settings page and share them with your app.
Base URL

https://arctracker.io

## Public Endpoints (No Auth Required)

These endpoints return static game data and require no authentication. Responses include all locales as multilingual objects (e.g., name: { en: "...", de: "...", ... }). Responses are cached and suitable for high-frequency requests.
GET
/api/items

All items with multilingual names, descriptions, and effects. Static response, no parameters.
GET
/api/quests

All quests with multilingual details, objectives, and rewards. Static response, no parameters.
GET
/api/hideout

All hideout modules with multilingual names, levels, and requirements. Static response, no parameters.
GET
/api/projects

All projects with multilingual names and phases. Supports season filtering.

### Parameters

season
Filter by season: 1, 2, or comma-separated (e.g., 1,2).
 
### Authentication

User data endpoints use a dual-key system. Your app sends both an app key and a user key with each request. This ensures users explicitly consent to sharing their data.
1Register your app

Go to the Developer Dashboard and register your app. You'll receive an app key (arc_k1_...) that identifies your application.
2User creates a personal key

Users go to Settings > Developer Access and create a personal API key (arc_u1_...) with the scopes they want to share.
3Send both keys with requests

Include the app key in the X-App-Key header and the user key in the Authorization: Bearer header.
Required Headers
X-App-Key
Your app's API key (from Developer Dashboard)
Authorization: Bearer <key>
The user's personal API key
Example Request

curl -H "X-App-Key: arc_k1_your_app_key" \
     -H "Authorization: Bearer arc_u1_user_key" \
     https://arctracker.io/api/v2/user/profile

Authenticated Endpoints (Dual-Key Required)

These endpoints return user-specific data and require both an app key and a user key.

### GET

/api/v2/user/profile
profile:read

Basic user profile information (username, level, member since).
GET
/api/v2/user/stash
stash:read

User's inventory/stash with enriched item data. Supports pagination.

### Parameters
locale
Language code (e.g., en, de, fr). Defaults to en.
page
### Page number for pagination (default: 1).
per_page
Items per page, max 100 (default: 50).
sort
Sort by: slot (default), name, quantity.
GET
/api/v2/user/loadout
loadout:read

User's current loadout with enriched equipment details.

### Parameters
locale
Language code (e.g., en, de, fr). Defaults to en.
GET
/api/v2/user/quests
quests:read

User's quest completion progress with optional filtering.

### Parameters
locale
Language code (e.g., en, de, fr). Defaults to en.
filter
Filter: completed, incomplete.
GET
/api/v2/user/hideout
hideout:read

User's hideout module upgrade progress.

### Parameters
locale
Language code (e.g., en, de, fr). Defaults to en.
GET
/api/v2/user/projects
projects:read

User's project phase completion progress.

### Parameters
locale
Language code (e.g., en, de, fr). Defaults to en.
season
Filter by season: 1, 2.
Rate Limits

Each app gets 500 requests per hour by default. Rate limit info is included in response headers. You can request a higher limit from the Developer Dashboard.
X-RateLimit-Limit
Maximum requests allowed per window.
X-RateLimit-Remaining
Requests remaining in current window.
X-RateLimit-Reset
Unix timestamp when the rate limit resets.
Error Codes

All error responses follow a standard format with an error code and message.
Code	Description
401	Missing or invalid API key(s). Check both app key and user key.
403	Insufficient scope or app suspended. The user key must include the required scope.
404	Resource not found or user has no data for this endpoint.
429	Rate limit exceeded. Wait for the reset time in the X-RateLimit-Reset header.
500	Internal server error. Please try again later.
Code Examples
cURL

curl -H "X-App-Key: arc_k1_your_app_key" \
     -H "Authorization: Bearer arc_u1_user_key" \
     "https://arctracker.io/api/v2/user/stash?locale=en&page=1&per_page=50"

JavaScript

const response = await fetch(
  "https://arctracker.io/api/v2/user/stash?locale=en",
  {
    headers: {
      "X-App-Key": "arc_k1_your_app_key",
      "Authorization": "Bearer arc_u1_user_key",
    },
  }
);
const { data, meta } = await response.json();
console.log(data.items);

### Python

import requests

response = requests.get(
    "https://arctracker.io/api/v2/user/stash",
    params={"locale": "en", "page": 1, "per_page": 50},
    headers={
        "X-App-Key": "arc_k1_your_app_key",
        "Authorization": "Bearer arc_u1_user_key",
    },
)
data = response.json()
print(data["data"]["items"])

Response Format

All authenticated endpoints return a consistent JSON envelope.
Success Response

{
  "data": { ... },
  "meta": {
    "requestId": "req_abc123"
  }
}

Error Response

{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded. Try again later."
  },
  "meta": {
    "requestId": "req_abc123"
  }
}
