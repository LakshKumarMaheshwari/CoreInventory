"""
CoreInventory - Inventory Management System
Backend: FastAPI
Bug-fixed and validated version
"""

from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import uuid
import random
import re
from datetime import datetime, date

app = FastAPI(title="CoreInventory API", version="3.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------
# In-memory database
# -----------------------

users_db = {}
otp_db = {}
products_db = []

warehouses_db = [
    {"id": "W1", "name": "Main Warehouse", "short_code": "W1", "address": ""}
]

locations_db = [
    {"id": "L1", "name": "Main Store", "short_code": "MS", "warehouse_id": "W1"},
    {"id": "L2", "name": "Production Rack", "short_code": "PR", "warehouse_id": "W1"},
]

receipts_db = []
deliveries_db = []
moves_db = []

_ref_in = 0
_ref_out = 0
_ref_transfer = 0


# -----------------------
# Helper Functions
# -----------------------

def next_ref(op: str) -> str:
    global _ref_in, _ref_out, _ref_transfer

    wh = warehouses_db[0]["short_code"] if warehouses_db else "WH"

    if op == "IN":
        _ref_in += 1
        return f"{wh}/IN/{_ref_in:04d}"

    if op == "TRANSFER":
        _ref_transfer += 1
        return f"{wh}/TRF/{_ref_transfer:04d}"

    _ref_out += 1
    return f"{wh}/OUT/{_ref_out:04d}"


def get_product(pid: str):

    p = next((x for x in products_db if x["id"] == pid), None)

    if not p:
        raise HTTPException(status_code=404, detail="Product not found")

    return p


def validate_location(name: str):

    if not any(l["name"] == name for l in locations_db):
        raise HTTPException(status_code=404, detail=f"Location {name} not found")


def validate_qty(qty: int):

    if qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")


def ensure_locations(product: dict):

    if "locations" not in product:
        product["locations"] = {}

    if not product["locations"] and product.get("on_hand", 0) > 0:
        default = locations_db[0]["name"]
        product["locations"][default] = product["on_hand"]


# -----------------------
# Models
# -----------------------

class UserRegister(BaseModel):
    login_id: str
    email: str
    password: str
    confirm_password: str


class UserLogin(BaseModel):
    login_id: str
    password: str


class OTPRequest(BaseModel):
    email: str


class PasswordReset(BaseModel):
    email: str
    otp: str
    new_password: str


class ProductCreate(BaseModel):
    name: str
    per_unit_cost: float = 0
    on_hand: int = 0
    free_to_use: Optional[int] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    per_unit_cost: Optional[float] = None
    on_hand: Optional[int] = None
    free_to_use: Optional[int] = None


class WarehouseCreate(BaseModel):
    name: str
    short_code: str
    address: Optional[str] = ""


class LocationCreate(BaseModel):
    name: str
    short_code: str
    warehouse_id: str


class ReceiptCreate(BaseModel):
    receive_from: str
    contact: str
    to_location: Optional[str] = "Main Store"
    products: List[dict]


class TransferCreate(BaseModel):
    product_id: str
    from_location: str
    to_location: str
    qty: int


class AdjustmentCreate(BaseModel):
    product_id: str
    location: str
    qty_change: int
    reason: Optional[str] = ""


class DeliveryCreate(BaseModel):
    delivery_address: str
    contact: str
    from_location: Optional[str] = "Main Store"
    products: List[dict]


# -----------------------
# Root
# -----------------------

@app.get("/")
async def root():
    index = Path(__file__).parent / "index.html"

    if index.exists():
        return FileResponse(index)

    return {"message": "CoreInventory API Running"}


@app.get("/api/health")
async def health():
    return {"status": "online", "version": "3.1"}


# -----------------------
# Authentication
# -----------------------

def validate_login_id(login_id: str):

    if len(login_id) < 6 or len(login_id) > 12:
        raise HTTPException(status_code=400, detail="Login ID must be 6-12 characters")


def validate_password(password: str):

    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password too short")

    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="Password must contain uppercase")

    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="Password must contain lowercase")

    if not re.search(r"[!@#$%^&*]", password):
        raise HTTPException(status_code=400, detail="Password must contain special char")


@app.post("/api/register")
async def register(u: UserRegister):

    lid = u.login_id.strip()

    validate_login_id(lid)
    validate_password(u.password)

    if lid in users_db:
        raise HTTPException(status_code=400, detail="Login already exists")

    if u.password != u.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords mismatch")

    users_db[lid] = {
        "password": u.password,
        "email": u.email,
        "name": lid
    }

    return {"user_name": lid, "user_email": u.email}


@app.post("/api/login")
async def login(u: UserLogin):

    lid = u.login_id.strip()

    stored = users_db.get(lid)

    if not stored or stored["password"] != u.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "user_name": stored["name"],
        "user_email": stored["email"],
        "login_id": lid
    }


# -----------------------
# Products
# -----------------------

@app.get("/api/products")
async def get_products(search: Optional[str] = Query(None)):

    if not search:
        return {"products": products_db}

    s = search.lower()

    return {
        "products": [p for p in products_db if s in p["name"].lower()]
    }


@app.post("/api/products")
async def create_product(p: ProductCreate):

    if p.on_hand < 0:
        raise HTTPException(status_code=400, detail="Stock cannot be negative")

    fid = p.free_to_use if p.free_to_use is not None else p.on_hand

    new_p = {
        "id": str(uuid.uuid4()),
        "name": p.name,
        "per_unit_cost": p.per_unit_cost,
        "on_hand": p.on_hand,
        "free_to_use": fid,
        "locations": {"Main Store": p.on_hand} if p.on_hand else {}
    }

    products_db.append(new_p)

    return new_p


# -----------------------
# Transfers
# -----------------------

@app.post("/api/transfers")
async def create_transfer(t: TransferCreate):

    validate_qty(t.qty)

    validate_location(t.from_location)
    validate_location(t.to_location)

    if t.from_location == t.to_location:
        raise HTTPException(status_code=400, detail="Locations must differ")

    p = get_product(t.product_id)

    ensure_locations(p)

    avail = p["locations"].get(t.from_location, 0)

    if avail < t.qty:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    p["locations"][t.from_location] -= t.qty
    p["locations"][t.to_location] = p["locations"].get(t.to_location, 0) + t.qty

    ref = next_ref("TRANSFER")

    moves_db.append({
        "reference": ref,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "product": p["name"],
        "qty": t.qty,
        "from_loc": t.from_location,
        "to_loc": t.to_location,
        "type": "Transfer",
        "status": "Done"
    })

    return {"reference": ref}
