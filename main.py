from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import uuid
import random
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATABASE STRUCTURE (MODULAR IMS) ---
users_db = {} # {email: {password, name}}
otp_db = {}   # {email: otp_code}
products_db = [] 
operations_db = [] 
ledger_db = [] 

class UserAuth(BaseModel):
    email: str
    password: str
    name: Optional[str] = None

class OTPRequest(BaseModel):
    email: str

class PasswordReset(BaseModel):
    email: str
    otp: str
    new_password: str

class ProductCreate(BaseModel):
    sku: str
    name: str
    category: str
    uom: str
    initial_stock: int = 0
    location: str = "Main Warehouse"
    min_qty: int = 5

class OperationCreate(BaseModel):
    type: str 
    partner: Optional[str] = "Internal"
    product_id: str
    qty: int
    from_loc: Optional[str] = None
    to_loc: Optional[str] = None
    status: str = "Done"

# --- CORE LOGIC ---

def update_stock(product_id: str, qty: int, loc: str, increase: bool = True):
    product = next((p for p in products_db if p["id"] == product_id), None)
    if not product: return
    
    if loc not in product["locations"]:
        product["locations"][loc] = 0
        
    if increase:
        product["locations"][loc] += qty
        product["total_qty"] += qty
    else:
        product["locations"][loc] -= qty
        product["total_qty"] -= qty

def log_transaction(op_type: str, prod_name: str, qty: int, uom: str, f_loc: str, t_loc: str):
    ledger_db.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "type": op_type,
        "product": prod_name,
        "qty": qty,
        "uom": uom,
        "route": f"{f_loc} → {t_loc}"
    })

# --- AUTH ROUTES ---

@app.get("/")
async def health():
    return {"status": "online", "version": "IMS-v2.1"}

@app.post("/register")
async def register(user: UserAuth):
    if user.email in users_db:
        raise HTTPException(status_code=400, detail="User already exists")
    users_db[user.email] = {"password": user.password, "name": user.name}
    return {"user_name": user.name, "user_email": user.email}

@app.post("/login")
async def login(user: UserAuth):
    stored = users_db.get(user.email)
    if not stored or stored["password"] != user.password:
        raise HTTPException(status_code=401, detail="Invalid Credentials")
    return {"user_name": stored["name"], "user_email": user.email}

@app.post("/request-otp")
async def request_otp(req: OTPRequest):
    if req.email not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate a 6-digit OTP
    otp = str(random.randint(100000, 999999))
    otp_db[req.email] = otp
    print(f"DEBUG: OTP for {req.email} is {otp}") # Simulating sending email
    return {"message": "OTP sent to your email (Check console for mock OTP)"}

@app.post("/reset-password")
async def reset_password(req: PasswordReset):
    if req.email not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    
    if otp_db.get(req.email) != req.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    users_db[req.email]["password"] = req.new_password
    del otp_db[req.email]
    return {"message": "Password reset successfully. You can now login."}

# --- PRODUCT MANAGEMENT ---
@app.get("/products")
async def get_products():
    return {"products": products_db}

@app.post("/products")
async def create_product(p: ProductCreate):
    new_p = {
        "id": str(uuid.uuid4()),
        "sku": p.sku,
        "name": p.name,
        "category": p.category,
        "uom": p.uom,
        "total_qty": p.initial_stock,
        "locations": {p.location: p.initial_stock},
        "min_qty": p.min_qty
    }
    products_db.append(new_p)
    if p.initial_stock > 0:
        log_transaction("Initial Setup", p.name, p.initial_stock, p.uom, "External", p.location)
    return new_p

# --- OPERATIONS ---
@app.get("/operations")
async def get_ops():
    return {"operations": operations_db}

@app.post("/operations")
async def process_operation(op: OperationCreate):
    product = next((p for p in products_db if p["id"] == op.product_id), None)
    if not product: raise HTTPException(status_code=404, detail="Product not found")

    if op.type == "Receipt":
        update_stock(op.product_id, op.qty, op.to_loc, True)
        log_transaction("Receipt", product["name"], op.qty, product["uom"], op.partner, op.to_loc)
    
    elif op.type == "Delivery":
        if product["locations"].get(op.from_loc, 0) < op.qty:
            raise HTTPException(status_code=400, detail="Insufficient Stock at Location")
        update_stock(op.product_id, op.qty, op.from_loc, False)
        log_transaction("Delivery", product["name"], op.qty, product["uom"], op.from_loc, op.partner)

    elif op.type == "Transfer":
        if product["locations"].get(op.from_loc, 0) < op.qty:
            raise HTTPException(status_code=400, detail="Insufficient Stock for Transfer")
        product["locations"][op.from_loc] -= op.qty
        if op.to_loc not in product["locations"]: product["locations"][op.to_loc] = 0
        product["locations"][op.to_loc] += op.qty
        log_transaction("Transfer", product["name"], op.qty, product["uom"], op.from_loc, op.to_loc)

    elif op.type == "Adjustment":
        diff = op.qty - product["locations"].get(op.to_loc, 0)
        product["total_qty"] += diff
        product["locations"][op.to_loc] = op.qty
        log_transaction("Adjustment", product["name"], op.qty, product["uom"], "Audit", op.to_loc)

    new_op = {"id": str(uuid.uuid4()), **op.dict(), "date": datetime.now().strftime("%Y-%m-%d")}
    operations_db.append(new_op)
    return new_op

@app.get("/ledger")
async def get_ledger():
    return {"ledger": ledger_db[::-1]}

@app.get("/stats")
async def get_stats():
    return {
        "total_products": len(products_db),
        "low_stock": len([p for p in products_db if p["total_qty"] < p["min_qty"]]),
        "pending_receipts": len([o for o in operations_db if o["type"] == "Receipt" and o["status"] != "Done"]),
        "pending_deliveries": len([o for o in operations_db if o["type"] == "Delivery" and o["status"] != "Done"]),
        "scheduled_transfers": len([o for o in operations_db if o["type"] == "Transfer" and o["status"] != "Done"]),
        "total_stock": sum(p["total_qty"] for p in products_db)
    }
