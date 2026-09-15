from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

import models, schemas, database
from database import engine, get_db

# Crear tablas en la base de datos si no existen
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="DroguIA API")

# --- CONFIGURACIÓN DE CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- RUTAS PRINCIPALES ---

@app.get("/")
def read_root():
    return {"message": "Bienvenido a la API de DroguIA"}

# --- CLIENTES ---

@app.get("/clientes/", response_model=List[schemas.ClienteResponse], summary="Obtener Clientes")
def obtener_clientes(db: Session = Depends(get_db)):
    return db.query(models.Cliente).all()

@app.post("/clientes/", response_model=schemas.ClienteResponse, status_code=status.HTTP_201_CREATED, summary="Crear Cliente")
def crear_cliente(cliente: schemas.ClienteCreate, db: Session = Depends(get_db)):
    db_cliente = db.query(models.Cliente).filter(models.Cliente.cedula == cliente.cedula).first()
    if db_cliente:
        raise HTTPException(status_code=400, detail="La cédula ya está registrada.")
    nuevo_cliente = models.Cliente(**cliente.model_dump())
    db.add(nuevo_cliente)
    db.commit()
    db.refresh(nuevo_cliente)
    return nuevo_cliente

@app.post("/clientes/abono/", summary="Registrar Abono")
def registrar_abono(abono: schemas.AbonoCreate, db: Session = Depends(get_db)):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == abono.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    if abono.monto <= 0:
        raise HTTPException(status_code=400, detail="El monto del abono debe ser mayor a 0.")
    if abono.monto > cliente.deuda_actual:
        raise HTTPException(status_code=400, detail="El abono no puede superar la deuda actual.")

    cliente.deuda_actual -= abono.monto
    nuevo_abono = models.Abono(cliente_id=abono.cliente_id, monto=abono.monto)
    db.add(nuevo_abono)
    
    # Registrar en caja si está abierta
    caja_hoy = db.query(models.CajaDiaria).filter(models.CajaDiaria.fecha == date.today()).first()
    if caja_hoy and caja_hoy.estado == "abierta":
        caja_hoy.monto_final += abono.monto

    db.commit()
    return {"message": "Abono registrado con éxito", "deuda_actual": cliente.deuda_actual}

# --- CAJA ---

@app.get("/caja/estado/", summary="Estado Caja")
def estado_caja(db: Session = Depends(get_db)):
    caja_hoy = db.query(models.CajaDiaria).filter(models.CajaDiaria.fecha == date.today()).first()
    if not caja_hoy:
        return {"estado": "cerrada", "monto_inicial": 0.0, "monto_final": 0.0}
    return caja_hoy

@app.post("/caja/abrir/", summary="Abrir Caja")
def abrir_caja(datos: schemas.CajaAbrir, db: Session = Depends(get_db)):
    caja_hoy = db.query(models.CajaDiaria).filter(models.CajaDiaria.fecha == date.today()).first()
    if caja_hoy and caja_hoy.estado == "abierta":
        raise HTTPException(status_code=400, detail="La caja ya se encuentra abierta hoy.")
    
    if not caja_hoy:
        caja_hoy = models.CajaDiaria(fecha=date.today(), monto_inicial=datos.monto_inicial, monto_final=datos.monto_inicial, estado="abierta")
        db.add(caja_hoy)
    else:
        caja_hoy.monto_inicial = datos.monto_inicial
        caja_hoy.monto_final = datos.monto_inicial
        caja_hoy.estado = "abierta"
        
    db.commit()
    return {"message": "Caja abierta exitosamente", "monto_inicial": datos.monto_inicial}

@app.post("/caja/cerrar/", summary="Cerrar Caja")
def cerrar_caja(db: Session = Depends(get_db)):
    caja_hoy = db.query(models.CajaDiaria).filter(models.CajaDiaria.fecha == date.today()).first()
    if not caja_hoy or caja_hoy.estado == "cerrada":
        raise HTTPException(status_code=400, detail="La caja no está abierta hoy.")
    
    caja_hoy.estado = "cerrada"
    db.commit()
    return {"message": "Caja cerrada exitosamente", "monto_final": caja_hoy.monto_final}

# --- PRODUCTOS ---

@app.get("/productos/", response_model=List[schemas.ProductoResponse], summary="Obtener Productos")
def obtener_productos(db: Session = Depends(get_db)):
    return db.query(models.Producto).all()

@app.post("/productos/", response_model=schemas.ProductoResponse, status_code=status.HTTP_201_CREATED, summary="Crear Producto")
def crear_producto(producto: schemas.ProductoCreate, db: Session = Depends(get_db)):
    nuevo_prod = models.Producto(**producto.model_dump())
    db.add(nuevo_prod)
    db.commit()
    db.refresh(nuevo_prod)
    return nuevo_prod