"""
CoreInventory - Modular Inventory Management System
Backend: FastAPI + Python
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import uuid
import random
from datetime import datetime

app = FastAPI(title="CoreInventory API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-memory data stores ---
users_db = {}
otp_db = {}
products_db = []
operations_db = []
ledger_db = []
warehouses_db = ["Main Warehouse", "Production Floor", "Rack A", "Rack B"]


# --- Pydantic models ---
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
    category: str = "General"
    uom: str = "Units"
    initial_stock: int = 0
    location: str = "Main Warehouse"
    min_qty: int = 5


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    uom: Optional[str] = None
    min_qty: Optional[int] = None


class OperationCreate(BaseModel):
    type: str  # Receipt | Delivery | Transfer | Adjustment
    partner: Optional[str] = "Internal"
    product_id: str
    qty: int
    from_loc: Optional[str] = None
    to_loc: Optional[str] = None
    status: str = "Done"


class WarehouseCreate(BaseModel):
    name: str


# --- Core logic ---
def update_stock(product_id: str, qty: int, loc: str, increase: bool = True):
    product = next((p for p in products_db if p["id"] == product_id), None)
    if not product:
        return
    if loc not in product["locations"]:
        product["locations"][loc] = 0
    if increase:
        product["locations"][loc] += qty
        product["total_qty"] += qty
    else:
        product["locations"][loc] = max(0, product["locations"][loc] - qty)
        product["total_qty"] = max(0, product["total_qty"] - qty)


def log_transaction(op_type: str, prod_name: str, qty: int, uom: str, f_loc: str, t_loc: str):
    ledger_db.append({
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "type": op_type,
        "product": prod_name,
        "qty": qty,
        "uom": uom,
        "route": f"{f_loc} → {t_loc}",
    })


# --- Auth routes ---
@app.get("/")
async def root():
    return FileResponse(Path(__file__).parent / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "online", "version": "CoreInventory v1.0"}


@app.post("/api/register")
async def register(user: UserAuth):
    if user.email in users_db:
        raise HTTPException(status_code=400, detail="User already exists")
    users_db[user.email] = {"password": user.password, "name": user.name or "User"}
    return {"user_name": users_db[user.email]["name"], "user_email": user.email}


@app.post("/api/login")
async def login(user: UserAuth):
    stored = users_db.get(user.email)
    if not stored or stored["password"] != user.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"user_name": stored["name"], "user_email": user.email}


@app.post("/api/request-otp")
async def request_otp(req: OTPRequest):
    if req.email not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    otp = str(random.randint(100000, 999999))
    otp_db[req.email] = otp
    print(f"DEBUG OTP for {req.email}: {otp}")
    return {"message": "OTP sent. Check server console for mock OTP."}


@app.post("/api/reset-password")
async def reset_password(req: PasswordReset):
    if req.email not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    if otp_db.get(req.email) != req.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    users_db[req.email]["password"] = req.new_password
    otp_db.pop(req.email, None)
    return {"message": "Password reset successfully."}


# --- Product management ---
@app.get("/api/products")
async def get_products(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    items = products_db
    if category:
        items = [p for p in items if p.get("category") == category]
    if search:
        s = search.lower()
        items = [p for p in items if s in p.get("name", "").lower() or s in p.get("sku", "").lower()]
    return {"products": items}


@app.get("/api/products/{product_id}")
async def get_product(product_id: str):
    p = next((x for x in products_db if x["id"] == product_id), None)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return p


@app.post("/api/products")
async def create_product(p: ProductCreate):
    if any(x["sku"].upper() == p.sku.upper() for x in products_db):
        raise HTTPException(status_code=400, detail="SKU already exists")
    new_p = {
        "id": str(uuid.uuid4()),
        "sku": p.sku.upper(),
        "name": p.name,
        "category": p.category,
        "uom": p.uom,
        "total_qty": p.initial_stock,
        "locations": {p.location: p.initial_stock} if p.initial_stock else {},
        "min_qty": p.min_qty,
    }
    products_db.append(new_p)
    if p.initial_stock > 0:
        log_transaction("Initial", p.name, p.initial_stock, p.uom, "External", p.location)
    return new_p


@app.patch("/api/products/{product_id}")
async def update_product(product_id: str, body: ProductUpdate):
    p = next((x for x in products_db if x["id"] == product_id), None)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    if body.name is not None:
        p["name"] = body.name
    if body.category is not None:
        p["category"] = body.category
    if body.uom is not None:
        p["uom"] = body.uom
    if body.min_qty is not None:
        p["min_qty"] = body.min_qty
    return p


# --- Warehouses ---
@app.get("/api/warehouses")
async def get_warehouses():
    return {"warehouses": warehouses_db}


@app.post("/api/warehouses")
async def add_warehouse(body: WarehouseCreate):
    if body.name.strip() in warehouses_db:
        raise HTTPException(status_code=400, detail="Warehouse already exists")
    warehouses_db.append(body.name.strip())
    return {"warehouses": warehouses_db}


# --- Operations ---
@app.get("/api/operations")
async def get_operations(
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    items = operations_db
    if type:
        items = [o for o in items if o.get("type") == type]
    if status:
        items = [o for o in items if o.get("status") == status]
    return {"operations": list(reversed(items))}


@app.post("/api/operations")
async def process_operation(op: OperationCreate):
    product = next((p for p in products_db if p["id"] == op.product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    to_loc = op.to_loc or "Main Warehouse"
    from_loc = op.from_loc or "Main Warehouse"

    if op.type == "Receipt":
        update_stock(op.product_id, op.qty, to_loc, True)
        log_transaction("Receipt", product["name"], op.qty, product["uom"], op.partner or "Vendor", to_loc)

    elif op.type == "Delivery":
        avail = product["locations"].get(from_loc, 0)
        if avail < op.qty:
            raise HTTPException(status_code=400, detail=f"Insufficient stock at {from_loc} (available: {avail})")
        update_stock(op.product_id, op.qty, from_loc, False)
        log_transaction("Delivery", product["name"], op.qty, product["uom"], from_loc, op.partner or "Customer")

    elif op.type == "Transfer":
        avail = product["locations"].get(from_loc, 0)
        if avail < op.qty:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for transfer (available: {avail})")
        product["locations"][from_loc] = product["locations"].get(from_loc, 0) - op.qty
        product["locations"][to_loc] = product["locations"].get(to_loc, 0) + op.qty
        log_transaction("Transfer", product["name"], op.qty, product["uom"], from_loc, to_loc)

    elif op.type == "Adjustment":
        old_qty = product["locations"].get(to_loc, 0)
        product["locations"][to_loc] = op.qty
        product["total_qty"] = product["total_qty"] - old_qty + op.qty
        log_transaction("Adjustment", product["name"], op.qty - old_qty, product["uom"], "Audit", to_loc)

    else:
        raise HTTPException(status_code=400, detail="Invalid operation type")

    new_op = {
        "id": str(uuid.uuid4()),
        "type": op.type,
        "partner": op.partner,
        "product_id": op.product_id,
        "product_name": product["name"],
        "qty": op.qty,
        "from_loc": from_loc,
        "to_loc": to_loc,
        "status": "Done",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    operations_db.append(new_op)
    return new_op


# --- Ledger ---
@app.get("/api/ledger")
async def get_ledger(
    type: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
):
    items = ledger_db[::-1][:limit]
    if type:
        items = [l for l in items if l.get("type") == type]
    return {"ledger": items}


# --- Stats ---
@app.get("/api/stats")
async def get_stats():
    low = [p for p in products_db if p["total_qty"] < p["min_qty"]]
    return {
        "total_products": len(products_db),
        "low_stock": len(low),
        "out_of_stock": len([p for p in products_db if p["total_qty"] == 0]),
        "pending_receipts": len([o for o in operations_db if o["type"] == "Receipt" and o.get("status") != "Done"]),
        "pending_deliveries": len([o for o in operations_db if o["type"] == "Delivery" and o.get("status") != "Done"]),
        "scheduled_transfers": len([o for o in operations_db if o["type"] == "Transfer" and o.get("status") != "Done"]),
        "total_stock": sum(p["total_qty"] for p in products_db),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
