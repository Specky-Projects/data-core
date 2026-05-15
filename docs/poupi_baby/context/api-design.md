# API Design

## API Style

- REST API
- JSON responses
- Stateless architecture
- Versioned endpoints


## Base URL

/api/v1


## Authentication

- JWT Authentication
- Bearer Token
- OAuth2 (future)


## Response Pattern

### Success Response

```json
{
  "success": true,
  "data": {}
}
```
### Error Response
```json
{
  "success": false,
  "error": {
    "code": "PRODUCT_NOT_FOUND",
    "message": "Product not found"
  }
}
```
## Main Endpoints

### Products
- GET /products
- GET /products/:id
- GET /products/:id/history
---
### Search
- GET /search?q=
---
### Alerts
- POST /alerts
- GET /alerts
- DELETE /alerts/:id
---
### Authentication
- POST /auth/login
- POST /auth/register
- POST /auth/refresh
---
### Subscription
- GET /subscription
- POST /subscription/checkout
---
### Pagination
- GET /products?page=1&limit=20
---
### Filtering & Sorting
Supported query params:

- sort=price_asc
- sort=price_desc
- marketplace=
- minPrice=
- maxPrice=
- category=
---
### API Principles
- Consistent naming
- Pagination support
- Rate limiting
- Cache-friendly responses
- Input validation
---
### HTTP Status Codes
- 200 OK
- 201 Created
- 400 Bad Request
- 401 Unauthorized
- 403 Forbidden
- 404 Not Found
- 429 Too Many Requests
- 500 Internal Server Error