"""
CoreInventory - Inventory Management System
Backend: FastAPI - Matches wireframe: Dashboard, Operations (Receipt/Delivery/Adjustment),
Stock, Warehouse, Location, Move History
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

app = FastAPI(title="CoreInventory API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Data stores ---
users_db = {}  # login_id -> {password, email, name}
otp_db = {}
products_db = []
warehouses_db = [{"id": "W1", "name": "Main Warehouse", "short_code": "W1", "address": ""}]
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


# --- Models ---
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
    category: Optional[str] = ""
    sku: Optional[str] = ""
    unit_of_measure: Optional[str] = ""
    low_stock_threshold: Optional[int] = 0


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    per_unit_cost: Optional[float] = None
    on_hand: Optional[int] = None
    free_to_use: Optional[int] = None
    category: Optional[str] = None
    sku: Optional[str] = None
    unit_of_measure: Optional[str] = None
    low_stock_threshold: Optional[int] = None


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
    schedule_date: Optional[str] = None
    responsible: Optional[str] = ""
    login_id: Optional[str] = ""
    products: List[dict]  # [{product_id, qty}]


class TransferCreate(BaseModel):
    product_id: str
    from_location: str
    to_location: str
    qty: int


class AdjustmentCreate(BaseModel):
    product_id: str
    location: str
    qty_change: int  # negative for damage/loss
    reason: Optional[str] = ""


class ReceiptUpdate(BaseModel):
    receive_from: Optional[str] = None
    contact: Optional[str] = None
    schedule_date: Optional[str] = None
    responsible: Optional[str] = None
    status: Optional[str] = None
    products: Optional[List[dict]] = None


class DeliveryCreate(BaseModel):
    delivery_address: str
    contact: str
    from_location: Optional[str] = "Main Store"
    schedule_date: Optional[str] = None
    responsible: Optional[str] = ""
    operation_type: Optional[str] = "delivery"
    login_id: Optional[str] = ""
    products: List[dict]


class DeliveryUpdate(BaseModel):
    delivery_address: Optional[str] = None
    contact: Optional[str] = None
    schedule_date: Optional[str] = None
    responsible: Optional[str] = None
    status: Optional[str] = None
    products: Optional[List[dict]] = None


# --- Auth ---
@app.get("/")
async def root():
    return FileResponse(Path(_file_).parent / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "online", "version": "CoreInventory v3.0"}


def _validate_login_id(login_id: str) -> str:
    if len(login_id) < 6 or len(login_id) > 12:
        raise HTTPException(status_code=400, detail="Login ID must be 6-12 characters")
    return login_id


def _validate_password(password: str) -> str:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="Password must contain lowercase")
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="Password must contain uppercase")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise HTTPException(status_code=400, detail="Password must contain special character")
    return password


@app.post("/api/register")
async def register(u: UserRegister):
    lid = _validate_login_id(u.login_id.strip())
    if lid in users_db:
        raise HTTPException(status_code=400, detail="Login ID already exists")
    if u.email in [v.get("email") for v in users_db.values()]:
        raise HTTPException(status_code=400, detail="Email already registered")
    _validate_password(u.password)
    if u.password != u.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    users_db[lid] = {"password": u.password, "email": u.email, "name": u.login_id}
    return {"user_name": u.login_id, "user_email": u.email}


@app.post("/api/login")
async def login(u: UserLogin):
    stored = users_db.get(u.login_id.strip())
    if not stored or stored["password"] != u.password:
        raise HTTPException(status_code=401, detail="Invalid Login Id or Password")
    return {"user_name": stored["name"], "user_email": stored["email"], "login_id": u.login_id}


@app.post("/api/request-otp")
async def request_otp(req: OTPRequest):
    if not any(v.get("email") == req.email for v in users_db.values()):
        raise HTTPException(status_code=404, detail="User not found")
    otp = str(random.randint(100000, 999999))
    otp_db[req.email] = otp
    print(f"DEBUG OTP for {req.email}: {otp}")
    return {"message": "OTP sent"}


@app.post("/api/reset-password")
async def reset_password(req: PasswordReset):
    for lid, v in users_db.items():
        if v.get("email") == req.email:
            if otp_db.get(req.email) != req.otp:
                raise HTTPException(status_code=400, detail="Invalid OTP")
            users_db[lid]["password"] = _validate_password(req.new_password)
            otp_db.pop(req.email, None)
            return {"message": "Password reset successfully"}
    raise HTTPException(status_code=404, detail="User not found")


# --- Products ---
@app.get("/api/products")
async def get_products(search: Optional[str] = Query(None)):
    items = products_db
    if search:
        s = search.lower()
        items = [p for p in items if s in p.get("name", "").lower() or s in p.get("sku", "").lower()]
    return {"products": items}


@app.post("/api/products")
async def create_product(p: ProductCreate):
    fid = p.free_to_use if p.free_to_use is not None else p.on_hand
    loc_names = [loc["name"] for loc in locations_db]
    default_loc = loc_names[0] if loc_names else "Main Store"
    locations = {default_loc: p.on_hand} if p.on_hand else {}
    new_p = {
        "id": str(uuid.uuid4()),
        "name": p.name,
        "per_unit_cost": p.per_unit_cost,
        "on_hand": p.on_hand,
        "free_to_use": fid,
        "locations": locations,
        "category": p.category or "",
        "sku": p.sku or "",
        "unit_of_measure": p.unit_of_measure or "",
        "low_stock_threshold": p.low_stock_threshold or 0,
    }
    products_db.append(new_p)
    return new_p


@app.patch("/api/products/{product_id}")
async def update_product(product_id: str, body: ProductUpdate):
    p = next((x for x in products_db if x["id"] == product_id), None)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    _ensure_locations(p)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            p[k] = v
    return p


# --- Stock ---
@app.get("/api/stock")
async def get_stock():
    result = []
    for p in products_db:
        _ensure_locations(p)
        locs = p.get("locations", {})
        result.append({
            "product": p["name"],
            "product_id": p["id"],
            "per_unit_cost": p.get("per_unit_cost", 0),
            "on_hand": p.get("on_hand", 0),
            "free_to_use": p.get("free_to_use", p.get("on_hand", 0)),
            "locations": locs,
            "category": p.get("category", ""),
            "sku": p.get("sku", ""),
            "unit_of_measure": p.get("unit_of_measure", ""),
            "low_stock_threshold": p.get("low_stock_threshold", 0),
        })
    return {"stock": result}


# --- Warehouses ---
@app.get("/api/warehouses")
async def get_warehouses():
    return {"warehouses": warehouses_db}


@app.post("/api/warehouses")
async def add_warehouse(w: WarehouseCreate):
    new_w = {"id": str(uuid.uuid4()), "name": w.name, "short_code": w.short_code, "address": w.address or ""}
    warehouses_db.append(new_w)
    return new_w


# --- Locations ---
@app.get("/api/locations")
async def get_locations():
    return {"locations": locations_db}


@app.post("/api/locations")
async def add_location(l: LocationCreate):
    new_l = {"id": str(uuid.uuid4()), "name": l.name, "short_code": l.short_code, "warehouse_id": l.warehouse_id}
    locations_db.append(new_l)
    return new_l


# --- Receipts ---
@app.get("/api/receipts")
async def get_receipts(search: Optional[str] = Query(None), login_id: Optional[str] = Query(None)):
    items = list(reversed(receipts_db))
    if login_id:
        items = [r for r in items if r.get("login_id") == login_id]
    if search:
        s = search.lower()
        items = [r for r in items if s in (r.get("reference", "") or "").lower()
                 or s in (r.get("contact", "") or "").lower()]
    return {"receipts": items}


@app.get("/api/receipts/{receipt_id}")
async def get_receipt(receipt_id: str):
    r = next((x for x in receipts_db if x["id"] == receipt_id), None)
    if not r:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return r


def _ensure_locations(p: dict):
    if "locations" not in p:
        p["locations"] = {}
    loc_names = [loc["name"] for loc in locations_db]
    default = loc_names[0] if loc_names else "Main Store"
    if not p["locations"] and p.get("on_hand", 0) > 0:
        p["locations"][default] = p["on_hand"]


@app.post("/api/receipts")
async def create_receipt(r: ReceiptCreate):
    """Save as Draft only — no stock addition. Use /done to commit."""
    ref = next_ref("IN")
    to_loc = r.to_location or (locations_db[0]["name"] if locations_db else "Main Store")
    products = []
    for line in r.products:
        pid = line.get("product_id")
        qty = int(line.get("qty", 0))
        p = next((x for x in products_db if x["id"] == pid), None)
        if p and qty > 0:
            products.append({"product_id": pid, "product_name": p["name"], "qty": qty})
    new_r = {
        "id": str(uuid.uuid4()),
        "reference": ref,
        "from_loc": "vendor",
        "to_loc": to_loc,
        "contact": r.contact,
        "receive_from": r.receive_from,
        "schedule_date": r.schedule_date or "",
        "responsible": r.responsible or "",
        "login_id": r.login_id or "",
        "status": "Draft",
        "products": products,
    }
    receipts_db.append(new_r)
    return new_r


@app.post("/api/receipts/{receipt_id}/done")
async def complete_receipt(receipt_id: str):
    """Mark receipt Done — adds stock and logs the move."""
    r = next((x for x in receipts_db if x["id"] == receipt_id), None)
    if not r:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if r["status"] == "Done":
        raise HTTPException(status_code=400, detail="Receipt is already Done")
    to_loc = r["to_loc"]
    for line in r.get("products", []):
        pid = line.get("product_id")
        qty = int(line.get("qty", 0))
        p = next((x for x in products_db if x["id"] == pid), None)
        if not p:
            raise HTTPException(status_code=400, detail=f"Product {pid} not found")
        _ensure_locations(p)
        p["locations"][to_loc] = p["locations"].get(to_loc, 0) + qty
        p["on_hand"] = p.get("on_hand", 0) + qty
        p["free_to_use"] = p.get("free_to_use", 0) + qty
        moves_db.append({"reference": r["reference"], "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                         "contact": r.get("contact", ""), "from_loc": "vendor", "to_loc": to_loc,
                         "product": p["name"], "qty": qty, "type": "IN", "status": "Done"})
    r["status"] = "Done"
    return r


@app.patch("/api/receipts/{receipt_id}")
async def update_receipt(receipt_id: str, body: ReceiptUpdate):
    r = next((x for x in receipts_db if x["id"] == receipt_id), None)
    if not r:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if body.status == "Ready":
        r["status"] = "Ready"
    elif body.status == "Done":
        r["status"] = "Done"
    for k, v in body.model_dump(exclude_unset=True).items():
        if k != "status" and v is not None:
            r[k] = v
    return r


# --- Deliveries ---
@app.get("/api/deliveries")
async def get_deliveries(search: Optional[str] = Query(None), login_id: Optional[str] = Query(None)):
    items = list(reversed(deliveries_db))
    if login_id:
        items = [d for d in items if d.get("login_id") == login_id]
    if search:
        s = search.lower()
        items = [d for d in items if s in (d.get("reference", "") or "").lower()
                 or s in (d.get("contact", "") or "").lower()]
    return {"deliveries": items}


@app.get("/api/deliveries/{delivery_id}")
async def get_delivery(delivery_id: str):
    d = next((x for x in deliveries_db if x["id"] == delivery_id), None)
    if not d:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return d


@app.post("/api/deliveries")
async def create_delivery(d: DeliveryCreate):
    """Save as Draft only — no stock deduction. Use /done to commit."""
    ref = next_ref("OUT")
    from_loc = d.from_location or (locations_db[0]["name"] if locations_db else "Main Store")
    products = []
    for line in d.products:
        pid = line.get("product_id")
        qty = int(line.get("qty", 0))
        p = next((x for x in products_db if x["id"] == pid), None)
        if p:
            products.append({"product_id": pid, "product_name": p["name"], "qty": qty})
        else:
            products.append({"product_id": pid, "product_name": "?", "qty": qty})
    new_d = {
        "id": str(uuid.uuid4()),
        "reference": ref,
        "from_loc": from_loc,
        "to_loc": "vendor",
        "contact": d.contact,
        "delivery_address": d.delivery_address,
        "schedule_date": d.schedule_date or "",
        "responsible": d.responsible or "",
        "operation_type": d.operation_type or "delivery",
        "login_id": d.login_id or "",
        "status": "Draft",
        "products": products,
    }
    deliveries_db.append(new_d)
    return new_d


@app.post("/api/deliveries/{delivery_id}/done")
async def complete_delivery(delivery_id: str):
    """Mark delivery Done — deducts stock and logs the move."""
    d = next((x for x in deliveries_db if x["id"] == delivery_id), None)
    if not d:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if d["status"] == "Done":
        raise HTTPException(status_code=400, detail="Delivery is already Done")
    from_loc = d["from_loc"]
    for line in d.get("products", []):
        pid = line.get("product_id")
        qty = int(line.get("qty", 0))
        p = next((x for x in products_db if x["id"] == pid), None)
        if not p:
            raise HTTPException(status_code=400, detail=f"Product {pid} not found")
        _ensure_locations(p)
        avail = p["locations"].get(from_loc, 0)
        if avail < qty:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {p['name']} at {from_loc} (available: {avail})")
        p["locations"][from_loc] = p["locations"].get(from_loc, 0) - qty
        p["on_hand"] = p.get("on_hand", 0) - qty
        p["free_to_use"] = max(0, p.get("free_to_use", 0) - qty)
        moves_db.append({"reference": d["reference"], "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                         "contact": d.get("contact", ""), "from_loc": from_loc, "to_loc": "vendor",
                         "product": p["name"], "qty": qty, "type": "OUT", "status": "Done"})
    d["status"] = "Done"
    return d


@app.patch("/api/deliveries/{delivery_id}")
async def update_delivery(delivery_id: str, body: DeliveryUpdate):
    d = next((x for x in deliveries_db if x["id"] == delivery_id), None)
    if not d:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if body.status:
        d["status"] = body.status
    for k, v in body.model_dump(exclude_unset=True).items():
        if k != "status" and v is not None:
            d[k] = v
    return d


# --- Internal Transfer ---
@app.post("/api/transfers")
async def create_transfer(t: TransferCreate):
    p = next((x for x in products_db if x["id"] == t.product_id), None)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    _ensure_locations(p)
    avail = p["locations"].get(t.from_location, 0)
    if avail < t.qty:
        raise HTTPException(status_code=400, detail=f"Insufficient stock at {t.from_location} (available: {avail})")
    if t.from_location == t.to_location:
        raise HTTPException(status_code=400, detail="From and To locations must be different")
    p["locations"][t.from_location] = p["locations"].get(t.from_location, 0) - t.qty
    p["locations"][t.to_location] = p["locations"].get(t.to_location, 0) + t.qty
    ref = next_ref("TRANSFER")
    moves_db.append({"reference": ref, "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "contact": "Internal",
                     "from_loc": t.from_location, "to_loc": t.to_location, "product": p["name"], "qty": t.qty,
                     "type": "Transfer", "status": "Done"})
    return {"reference": ref, "product": p["name"], "qty": t.qty, "from": t.from_location, "to": t.to_location}


# --- Adjustment ---
@app.post("/api/adjustments")
async def create_adjustment(a: AdjustmentCreate):
    p = next((x for x in products_db if x["id"] == a.product_id), None)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    _ensure_locations(p)
    current = p["locations"].get(a.location, 0)
    new_qty = current + a.qty_change
    if new_qty < 0:
        raise HTTPException(status_code=400, detail=f"Adjustment would make stock negative at {a.location}")
    p["locations"][a.location] = new_qty
    p["on_hand"] = p.get("on_hand", 0) + a.qty_change
    p["free_to_use"] = max(0, p.get("free_to_use", 0) + a.qty_change)
    ref = f"ADJ-{datetime.now().strftime('%Y%m%d%H%M')}"
    moves_db.append({"reference": ref, "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "contact": a.reason or "Adjustment",
                     "from_loc": "Audit", "to_loc": a.location, "product": p["name"], "qty": a.qty_change,
                     "type": "Adjustment", "status": "Done"})
    return {"reference": ref, "product": p["name"], "location": a.location, "change": a.qty_change}


# --- Move History ---
@app.get("/api/moves")
async def get_moves(search: Optional[str] = Query(None)):
    items = list(reversed(moves_db))
    if search:
        s = search.lower()
        items = [m for m in items if s in (m.get("reference", "") or "").lower()
                 or s in (m.get("contact", "") or "").lower()
                 or s in (m.get("product", "") or "").lower()]
    return {"moves": items}


# --- Dashboard stats ---
@app.get("/api/stats")
async def get_stats():
    today = date.today().isoformat()
    rec_draft = [r for r in receipts_db if r.get("status") in ("Draft", "Ready")]
    rec_late = [r for r in rec_draft if r.get("schedule_date") and r["schedule_date"] < today]
    rec_ops = len([r for r in receipts_db if r.get("status") != "Done"])
    del_draft = [d for d in deliveries_db if d.get("status") in ("Draft", "Ready", "Waiting")]
    del_late = [d for d in del_draft if d.get("schedule_date") and d["schedule_date"] < today]
    del_wait = len([d for d in deliveries_db if d.get("status") == "Waiting"])
    del_ops = len([d for d in deliveries_db if d.get("status") != "Done"])
    total_products = len(products_db)
    low_stock = [p for p in products_db if p.get("low_stock_threshold", 0) > 0 and p.get("on_hand", 0) <= p.get("low_stock_threshold", 0) and p.get("on_hand", 0) > 0]
    out_of_stock = [p for p in products_db if p.get("on_hand", 0) == 0]
    pending_receipts = len([r for r in receipts_db if r.get("status") == "Draft"])
    pending_deliveries = len([d for d in deliveries_db if d.get("status") == "Draft"])
    return {
        "receipt_to_receive": len([r for r in receipts_db if r.get("status") == "Ready"]),
        "receipt_late": len(rec_late),
        "receipt_operations": rec_ops,
        "delivery_to_deliver": len([d for d in deliveries_db if d.get("status") == "Ready"]),
        "delivery_late": len(del_late),
        "delivery_waiting": del_wait,
        "delivery_operations": del_ops,
        "total_products": total_products,
        "low_stock_count": len(low_stock),
        "out_of_stock_count": len(out_of_stock),
        "pending_receipts": pending_receipts,
        "pending_deliveries": pending_deliveries,
        "low_stock_items": [{"name": p["name"], "on_hand": p["on_hand"], "threshold": p.get("low_stock_threshold", 0)} for p in low_stock],
        "out_of_stock_items": [{"name": p["name"]} for p in out_of_stock],
    }


if _name_ == "_main_":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
