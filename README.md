**Core Inventory**
A lightweight inventory management system built with FastAPI (backend) and vanilla HTML/CSS/JS (frontend). Supports multi-user authentication, receipts, deliveries, internal transfers, stock adjustments, and move history.



**Features**
Authentication — Sign up, sign in, forgot password (OTP-based reset), and sign out

Per-user data isolation — Receipts and deliveries are scoped to the logged-in user

Receipt management — Create receipts as Draft, then Mark as Done to add stock

Delivery management — Create deliveries as Draft, then Mark as Done to deduct stock

Internal Transfer — Move stock between locations without changing total on-hand

Stock Adjustment — Correct stock levels with a reason (supports negative adjustments)

Stock View — Per-product breakdown by location with editable unit cost

Move History — Full audit log of all IN / OUT / Transfer / Adjustment operations

Warehouses \& Locations — Add warehouses and sub-locations via Settings



**Project Structure**
The project is two files. main.py is the FastAPI backend containing all API routes and in-memory data stores. index.html is the single-page frontend covering login, the dashboard, and all views.


**Requirements**
Python 3.8+
FastAPI
Uvicorn


**Installation**
bashpip install fastapi uvicorn


**Running the App**
bashpython main.py
Then open your browser at http://localhost:8000.


**API Overview**
Auth

POST /api/register registers a new user. POST /api/login logs in. POST /api/request-otp sends a password reset OTP. POST /api/reset-password resets the password using that OTP.

Receipts

GET /api/receipts lists receipts filtered by the logged-in user. GET /api/receipts/{id} fetches a single receipt. POST /api/receipts creates a receipt saved as Draft. POST /api/receipts/{id}/done marks it as Done and adds stock. PATCH /api/receipts/{id} updates receipt fields.

Deliveries

GET /api/deliveries lists deliveries filtered by the logged-in user. GET /api/deliveries/{id} fetches a single delivery. POST /api/deliveries creates a delivery saved as Draft. POST /api/deliveries/{id}/done marks it as Done and deducts stock. PATCH /api/deliveries/{id} updates delivery fields.

Other Operations

POST /api/transfers moves stock between two locations without changing total on-hand. POST /api/adjustments corrects stock at a location and accepts negative values for losses or damage.

Products, Stock and Warehouses

GET /api/products and POST /api/products list and create products. PATCH /api/products/{id} updates a product. GET /api/stock returns stock levels with a per-location breakdown. GET /api/warehouses and POST /api/warehouses manage warehouses. GET /api/locations and POST /api/locations manage locations. GET /api/moves returns the full searchable move history. GET /api/stats returns dashboard summary counts.


**Receipt and Delivery Flow**
Both operations follow a two-step flow: Draft then Done. Clicking Save Draft records the operation without touching stock. Clicking Mark as Done commits the stock change and logs it in Move History. You can click any row in the Receipts or Deliveries table to reopen it and advance its status.


**Notes**
Data is stored in-memory and will reset when the server restarts. For persistence, replace the in-memory lists with a database such as SQLite via SQLAlchemy. OTPs for password reset are printed to the server console. The default warehouse and two locations (Main Store and Production Rack) are pre-loaded on startup.


