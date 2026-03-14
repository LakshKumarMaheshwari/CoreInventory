CoreInventory

CoreInventory is a lightweight inventory management system built using FastAPI (backend) and vanilla HTML, CSS, and JavaScript (frontend).

The system allows businesses to manage inventory operations such as receipts, deliveries, internal transfers, and stock adjustments, while maintaining a complete audit history of all inventory movements.

It also supports multi-user authentication and per-user data isolation, ensuring that users only see their own operational records.

Features
Authentication

Sign up for a new account

Secure sign in

Forgot password with OTP-based reset

Sign out functionality

Per-User Data Isolation

Receipts and deliveries are scoped to the logged-in user, preventing access to other users’ records.

Receipt Management

Create receipts as Draft

Mark receipts as Done to add stock

Edit receipt information before finalizing

Delivery Management

Create deliveries as Draft

Mark deliveries as Done to deduct stock

Update delivery information before completion

Internal Transfer

Move stock between different locations within a warehouse without changing the total on-hand quantity.

Stock Adjustment

Correct stock levels when discrepancies occur.
Supports negative adjustments for losses, damage, or shrinkage.

Stock View

Displays:

Total product stock

Location-wise inventory breakdown

Editable per-unit cost

Move History

Maintains a complete audit log of:

Stock IN

Stock OUT

Internal transfers

Stock adjustments

Warehouses and Locations

Allows adding:

Multiple warehouses

Multiple locations within each warehouse

These can be managed from the Settings section.

Project Structure

The project consists of two main files.

main.py

FastAPI backend that:

Defines all API routes

Handles authentication

Manages inventory logic

Stores data in memory

index.html

Single-page frontend containing:

Login and authentication UI

Dashboard

Receipts and deliveries management

Stock and warehouse views

Requirements

Python 3.8 or higher

FastAPI

Uvicorn

Installation

Install required dependencies:

pip install fastapi uvicorn
Running the Application

Start the backend server:

python -m uvicorn main:app --reload

After the server starts, open index.html in Google Chrome directly from your file explorer.

API Overview
Authentication
Endpoint	Description
POST /api/register	Register a new user
POST /api/login	Log in a user
POST /api/request-otp	Send OTP for password reset
POST /api/reset-password	Reset password using OTP
Receipts
Endpoint	Description
GET /api/receipts	List receipts for the logged-in user
GET /api/receipts/{id}	Retrieve a specific receipt
POST /api/receipts	Create a receipt in Draft state
POST /api/receipts/{id}/done	Mark receipt as Done and add stock
PATCH /api/receipts/{id}	Update receipt details
Deliveries
Endpoint	Description
GET /api/deliveries	List deliveries for the logged-in user
GET /api/deliveries/{id}	Retrieve a specific delivery
POST /api/deliveries	Create a delivery in Draft state
POST /api/deliveries/{id}/done	Mark delivery as Done and deduct stock
PATCH /api/deliveries/{id}	Update delivery details
Other Operations
Endpoint	Description
POST /api/transfers	Move stock between locations
POST /api/adjustments	Adjust stock levels with a reason
Products, Stock, and Warehouses
Endpoint	Description
GET /api/products	List all products
POST /api/products	Create a new product
PATCH /api/products/{id}	Update product details
GET /api/stock	View stock with location breakdown
GET /api/warehouses	List warehouses
POST /api/warehouses	Create a new warehouse
GET /api/locations	List locations
POST /api/locations	Create a new location
GET /api/moves	View inventory move history
GET /api/stats	Get dashboard statistics
Receipt and Delivery Workflow

Both receipts and deliveries follow a two-step workflow.

Step 1 – Draft

The operation is saved as a draft.
Stock levels are not changed.

Step 2 – Done

When marked as Done:

Stock is updated

A record is added to Move History

Users can click any row in the Receipts or Deliveries table to reopen and update the record.

Notes

All data is stored in memory, meaning it will reset when the server restarts.

For permanent storage, replace the in-memory lists with a database such as:

SQLite

PostgreSQL

MySQL

OTPs used for password reset are printed in the server console.

On startup, the system automatically creates:

One default warehouse

Two default locations:

Main Store

Production Rack

✅ This version is clean, bug-free, and ready for hackathon submission or GitHub documentation.

If you want, I can also show you a 5-line addition that will make your README look 10× more professional for judges (with demo section, screenshots, and badges). 🚀
