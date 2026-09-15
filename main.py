from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import date

import models
import schemas
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="DroguIA API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "API DroguIA funcionando correctamente"}

# ==========================================
# ESQUEMAS PARA VENTAS / POS
# ==========================================
class DetalleVentaSchema(BaseModel):
    producto_id: int
    cantidad: int

class VentaSchema(BaseModel):
    items: List[DetalleVentaSchema]
    tipo_pago: str  # "efectivo", "nequi", "daviplata", "tarjeta"

# ==========================================
# RUTAS DE PRODUCTOS / INVENTARIO
# ==========================================
@app.get("/productos/", response_model=List[schemas.ProductoResponse])
def listar_productos(db: Session = Depends(get_db)):
    return db.query(models.Producto).all()

@app.post("/productos/", response_model=schemas.ProductoResponse)
def crear_producto(producto: schemas.ProductoCreate, db: Session = Depends(get_db)):
    db_producto = models.Producto(**producto.dict())
    db.add(db_producto)
    db.commit()
    db.refresh(db_producto)
    return db_producto

@app.delete("/productos/{producto_id}")
def eliminar_producto(producto_id: int, db: Session = Depends(get_db)):
    prod = db.query(models.Producto).filter(models.Producto.id == producto_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    db.delete(prod)
    db.commit()
    return {"message": "Producto eliminado con éxito"}

# ==========================================
# RUTAS DE CAJA Y BALANCE
# ==========================================
@app.get("/caja/estado/")
def obtener_estado_caja(db: Session = Depends(get_db)):
    caja_abierta = db.query(models.Caja).filter(models.Caja.estado == "abierta").first()
    if caja_abierta:
        return {
            "estado": "abierta",
            "monto_inicial": caja_abierta.monto_inicial,
            "monto_final": caja_abierta.monto_final
        }
    return {"estado": "cerrada", "monto_inicial": 0.0, "monto_final": 0.0}

@app.post("/caja/abrir/")
def abrir_caja(datos: schemas.CajaAbrir, db: Session = Depends(get_db)):
    caja_abierta = db.query(models.Caja).filter(models.Caja.estado == "abierta").first()
    if caja_abierta:
        raise HTTPException(status_code=400, detail="Ya existe una caja abierta")
    
    nueva_caja = models.Caja(
        monto_inicial=datos.monto_inicial,
        monto_final=datos.monto_inicial,
        estado="abierta"
    )
    db.add(nueva_caja)
    db.commit()
    return {"message": "Caja abierta con éxito"}

@app.post("/caja/cerrar/")
def cerrar_caja(db: Session = Depends(get_db)):
    caja_abierta = db.query(models.Caja).filter(models.Caja.estado == "abierta").first()
    if not caja_abierta:
        raise HTTPException(status_code=400, detail="No hay ninguna caja abierta para cerrar")
    
    caja_abierta.estado = "cerrada"
    db.commit()
    return {"message": "Caja cerrada con éxito"}

# ==========================================
# RUTAS DE CLIENTES Y CRÉDITOS
# ==========================================
@app.get("/clientes/", response_model=List[schemas.ClienteResponse])
def listar_clientes(db: Session = Depends(get_db)):
    return db.query(models.Cliente).all()

@app.post("/clientes/", response_model=schemas.ClienteResponse)
def crear_cliente(cliente: schemas.ClienteCreate, db: Session = Depends(get_db)):
    db_cliente = models.Cliente(**cliente.dict())
    db.add(db_cliente)
    db.commit()
    db.refresh(db_cliente)
    return db_cliente

@app.post("/clientes/abono/")
def registrar_abono(datos: schemas.AbonoCliente, db: Session = Depends(get_db)):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == datos.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    caja = db.query(models.Caja).filter(models.Caja.estado == "abierta").first()
    if not caja:
        raise HTTPException(status_code=400, detail="Debe abrir la caja antes de recibir abonos")
    
    cliente.deuda_actual -= datos.monto
    if cliente.deuda_actual < 0:
        cliente.deuda_actual = 0.0

    caja.monto_final += datos.monto
    db.commit()
    return {"message": "Abono registrado con éxito"}

@app.delete("/clientes/{cliente_id}")
def eliminar_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cli = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not cli:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    db.delete(cli)
    db.commit()
    return {"message": "Cliente eliminado con éxito"}

# ==========================================
# RUTA DE VENTAS / POS (MOSTRADOR)
# ==========================================
@app.post("/ventas/")
def registrar_venta(venta: VentaSchema, db: Session = Depends(get_db)):
    caja = db.query(models.Caja).filter(models.Caja.estado == "abierta").first()
    if not caja:
        raise HTTPException(status_code=400, detail="Debe abrir la caja antes de realizar ventas.")

    total_venta = 0.0

    for item in venta.items:
        prod = db.query(models.Producto).filter(models.Producto.id == item.producto_id).first()
        if not prod:
            raise HTTPException(status_code=404, detail=f"Producto ID {item.producto_id} no encontrado")
        if prod.stock < item.cantidad:
            raise HTTPException(status_code=400, detail=f"Stock insuficiente para {prod.nombre}. Disponible: {prod.stock}")
        
        prod.stock -= item.cantidad
        total_venta += prod.precio * item.cantidad

    caja.monto_final += total_venta

    db.commit()
    return {"message": "Venta registrada con éxito", "total": total_venta}