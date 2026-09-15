from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel

SQLALCHEMY_DATABASE_URL = "sqlite:///./droguia.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    cedula = Column(String, unique=True, index=True)
    telefono = Column(String, nullable=True)
    saldo_deuda = Column(Float, default=0.0)
    limite_credito = Column(Float, default=500000.0)
    
    ventas = relationship("Venta", back_populates="cliente")
    abonos = relationship("AbonoCliente", back_populates="cliente")

class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    codigo_barras = Column(String, unique=True, index=True)
    costo = Column(Float)
    precio = Column(Float)
    stock = Column(Integer)
    fecha_vencimiento = Column(DateTime, nullable=True)

class Caja(Base):
    __tablename__ = "cajas"

    id = Column(Integer, primary_key=True, index=True)
    fecha_apertura = Column(DateTime, default=datetime.now)
    fecha_cierre = Column(DateTime, nullable=True)
    monto_inicial = Column(Float)
    monto_final = Column(Float, nullable=True)
    estado = Column(String, default="ABIERTA")

class Venta(Base):
    __tablename__ = "ventas"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime, default=datetime.now)
    total = Column(Float)
    ganancia_total = Column(Float)
    metodo_pago = Column(String, default="Efectivo")
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    
    cliente = relationship("Cliente", back_populates="ventas")
    detalles = relationship("DetalleVenta", back_populates="venta")

class AbonoCliente(Base):
    __tablename__ = "abonos_cliente"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"))
    fecha = Column(DateTime, default=datetime.now)
    monto = Column(Float)
    metodo_pago = Column(String, default="Efectivo")

    cliente = relationship("Cliente", back_populates="abonos")

class DetalleVenta(Base):
    __tablename__ = "detalles_venta"

    id = Column(Integer, primary_key=True, index=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"))
    producto_id = Column(Integer, ForeignKey("productos.id"))
    cantidad = Column(Integer)
    precio_unitario = Column(Float)
    costo_unitario = Column(Float)
    subtotal = Column(Float)
    
    venta = relationship("Venta", back_populates="detalles")
    producto = relationship("Producto")

Base.metadata.create_all(bind=engine)

# Schemas
class ClienteCrear(BaseModel):
    nombre: str
    cedula: str
    telefono: Optional[str] = None
    limite_credito: Optional[float] = 500000.0

class AbonoCrear(BaseModel):
    cliente_id: int
    monto: float
    metodo_pago: Optional[str] = "Efectivo"

class ProductoCrear(BaseModel):
    nombre: str
    codigo_barras: str
    costo: float
    precio: float
    stock: int
    fecha_vencimiento: Optional[str] = None

class ItemCarrito(BaseModel):
    producto_id: int
    cantidad: int

class VentaCrear(BaseModel):
    items: List[ItemCarrito]
    metodo_pago: Optional[str] = "Efectivo"
    cliente_id: Optional[int] = None

class AbrirCaja(BaseModel):
    monto_inicial: float

class CerrarCaja(BaseModel):
    monto_final: float

app = FastAPI(title="DroguIA API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----- CLIENTES -----
@app.get("/clientes/")
def obtener_clientes(db: Session = Depends(get_db)):
    return db.query(Cliente).all()

@app.post("/clientes/")
def crear_cliente(cliente: ClienteCrear, db: Session = Depends(get_db)):
    existente = db.query(Cliente).filter(Cliente.cedula == cliente.cedula).first()
    if existente:
        raise HTTPException(status_code=400, detail="Ya existe un cliente registrado con esa cédula.")
    nuevo_cliente = Cliente(
        nombre=cliente.nombre,
        cedula=cliente.cedula,
        telefono=cliente.telefono,
        limite_credito=cliente.limite_credito or 500000.0
    )
    db.add(nuevo_cliente)
    db.commit()
    db.refresh(nuevo_cliente)
    return nuevo_cliente

@app.post("/clientes/abono/")
def registrar_abono(abono: AbonoCrear, db: Session = Depends(get_db)):
    caja_activa = db.query(Caja).filter(Caja.estado == "ABIERTA").first()
    if not caja_activa:
        raise HTTPException(status_code=400, detail="No se pueden recibir abonos con la caja cerrada.")

    cliente = db.query(Cliente).filter(Cliente.id == abono.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    
    if abono.monto <= 0:
        raise HTTPException(status_code=400, detail="El monto del abono debe ser mayor a 0.")

    if abono.monto > cliente.saldo_deuda:
        raise HTTPException(status_code=400, detail=f"El abono no puede superar la deuda actual (${cliente.saldo_deuda:,.0f}).")

    cliente.saldo_deuda -= abono.monto

    nuevo_abono = AbonoCliente(
        cliente_id=cliente.id,
        monto=abono.monto,
        metodo_pago=abono.metodo_pago or "Efectivo"
    )
    db.add(nuevo_abono)
    db.commit()
    return {"mensaje": "Abono registrado con éxito", "saldo_restante": cliente.saldo_deuda}

# ----- CAJA -----
@app.get("/caja/estado/")
def estado_caja(db: Session = Depends(get_db)):
    caja_abierta = db.query(Caja).filter(Caja.estado == "ABIERTA").order_by(Caja.id.desc()).first()
    if not caja_abierta:
        return None
    return caja_abierta

@app.post("/caja/abrir/")
def abrir_caja(datos: AbrirCaja, db: Session = Depends(get_db)):
    caja_activa = db.query(Caja).filter(Caja.estado == "ABIERTA").first()
    if caja_activa:
        raise HTTPException(status_code=400, detail="Ya existe una caja abierta.")
    nueva_caja = Caja(monto_inicial=datos.monto_inicial)
    db.add(nueva_caja)
    db.commit()
    db.refresh(nueva_caja)
    return nueva_caja

@app.post("/caja/cerrar/")
def cerrar_caja(datos: CerrarCaja, db: Session = Depends(get_db)):
    caja_activa = db.query(Caja).filter(Caja.estado == "ABIERTA").order_by(Caja.id.desc()).first()
    if not caja_activa:
        raise HTTPException(status_code=400, detail="No hay ninguna caja abierta para cerrar.")
    caja_activa.monto_final = datos.monto_final
    caja_activa.fecha_cierre = datetime.now()
    caja_activa.estado = "CERRADA"
    db.commit()
    return {"mensaje": "Caja cerrada correctamente"}

# ----- PRODUCTOS -----
@app.get("/productos/")
def obtener_productos(db: Session = Depends(get_db)):
    return db.query(Producto).all()

@app.post("/productos/")
def crear_producto(producto: ProductoCrear, db: Session = Depends(get_db)):
    db_prod = db.query(Producto).filter(Producto.codigo_barras == producto.codigo_barras).first()
    if db_prod:
        raise HTTPException(status_code=400, detail="El código de barras ya existe.")
    
    fecha_venc_dt = None
    if producto.fecha_vencimiento and producto.fecha_vencimiento.strip() != "":
        try:
            fecha_venc_dt = datetime.strptime(producto.fecha_vencimiento, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha de vencimiento inválido. Use AAAA-MM-DD")

    nuevo_prod = Producto(
        nombre=producto.nombre,
        codigo_barras=producto.codigo_barras,
        costo=producto.costo,
        precio=producto.precio,
        stock=producto.stock,
        fecha_vencimiento=fecha_venc_dt
    )
    db.add(nuevo_prod)
    db.commit()
    db.refresh(nuevo_prod)
    return nuevo_prod

@app.get("/alertas/vencimientos/")
def alertas_vencimientos(dias: int = 60, db: Session = Depends(get_db)):
    fecha_limite = datetime.now() + timedelta(days=dias)
    productos_proximos = db.query(Producto).filter(
        Producto.fecha_vencimiento.isnot(None),
        Producto.fecha_vencimiento <= fecha_limite
    ).all()
    return productos_proximos

# ----- VENTAS -----
@app.post("/ventas/")
def registrar_venta(venta_in: VentaCrear, db: Session = Depends(get_db)):
    caja_activa = db.query(Caja).filter(Caja.estado == "ABIERTA").first()
    if not caja_activa:
        raise HTTPException(status_code=400, detail="No se pueden registrar ventas sin abrir la caja.")

    cliente_obj = None
    if venta_in.metodo_pago == "Crédito / Fiar":
        if not venta_in.cliente_id:
            raise HTTPException(status_code=400, detail="Debe seleccionar un cliente para ventas a Crédito/Fiado.")
        cliente_obj = db.query(Cliente).filter(Cliente.id == venta_in.cliente_id).first()
        if not cliente_obj:
            raise HTTPException(status_code=404, detail="Cliente no encontrado.")

    total_venta = 0.0
    ganancia_total = 0.0
    detalles_db = []
    detalles_respuesta = []

    for item in venta_in.items:
        prod = db.query(Producto).filter(Producto.id == item.producto_id).first()
        if not prod:
            raise HTTPException(status_code=404, detail=f"Producto con ID {item.producto_id} no encontrado")
        
        if prod.stock < item.cantidad:
            raise HTTPException(status_code=400, detail=f"Stock insuficiente para {prod.nombre}. Disponible: {prod.stock}")

        prod.stock -= item.cantidad

        subtotal = prod.precio * item.cantidad
        costo_total = prod.costo * item.cantidad
        
        total_venta += subtotal
        ganancia_total += (subtotal - costo_total)

        detalle = DetalleVenta(
            producto_id=prod.id,
            cantidad=item.cantidad,
            precio_unitario=prod.precio,
            costo_unitario=prod.costo,
            subtotal=subtotal
        )
        detalles_db.append(detalle)
        
        detalles_respuesta.append({
            "nombre": prod.nombre,
            "cantidad": item.cantidad,
            "precio_unitario": prod.precio,
            "subtotal": subtotal
        })

    if venta_in.metodo_pago == "Crédito / Fiar" and cliente_obj:
        if (cliente_obj.saldo_deuda + total_venta) > cliente_obj.limite_credito:
            raise HTTPException(status_code=400, detail=f"La venta supera el límite de crédito del cliente (${cliente_obj.limite_credito:,.0f}). Deuda actual: ${cliente_obj.saldo_deuda:,.0f}")
        cliente_obj.saldo_deuda += total_venta

    nueva_venta = Venta(
        total=total_venta,
        ganancia_total=ganancia_total,
        metodo_pago=venta_in.metodo_pago or "Efectivo",
        cliente_id=venta_in.cliente_id if venta_in.metodo_pago == "Crédito / Fiar" else None,
        detalles=detalles_db
    )
    db.add(nueva_venta)
    db.commit()
    db.refresh(nueva_venta)

    return {
        "mensaje": "Venta exitosa",
        "venta_id": nueva_venta.id,
        "fecha": nueva_venta.fecha.strftime("%Y-%m-%d %H:%M:%S"),
        "total": total_venta,
        "metodo_pago": nueva_venta.metodo_pago,
        "cliente_nombre": cliente_obj.nombre if cliente_obj else None,
        "detalles": detalles_respuesta
    }

# ----- BALANCE -----
@app.get("/reportes/balance/")
def obtener_balance(fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, db: Session = Depends(get_db)):
    query_ventas = db.query(Venta)
    
    if fecha_inicio and fecha_fin:
        try:
            inicio_dt = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query_ventas = query_ventas.filter(Venta.fecha >= inicio_dt, Venta.fecha <= fin_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")
            
    ventas = query_ventas.all()
    
    total_ingresos = sum(v.total for v in ventas if v.metodo_pago != "Crédito / Fiar")
    total_ganancia = sum(v.ganancia_total for v in ventas)
    total_transacciones = len(ventas)

    total_efectivo = sum(v.total for v in ventas if v.metodo_pago == "Efectivo")
    total_nequi = sum(v.total for v in ventas if v.metodo_pago == "Nequi")
    total_daviplata = sum(v.total for v in ventas if v.metodo_pago == "Daviplata")
    total_tarjeta = sum(v.total for v in ventas if v.metodo_pago == "Tarjeta")
    total_credito = sum(v.total for v in ventas if v.metodo_pago == "Crédito / Fiar")
    
    return {
        "total_ingresos": total_ingresos,
        "total_ganancia": total_ganancia,
        "total_transacciones": total_transacciones,
        "desglose_pagos": {
            "Efectivo": total_efectivo,
            "Nequi": total_nequi,
            "Daviplata": total_daviplata,
            "Tarjeta": total_tarjeta,
            "Crédito / Fiado": total_credito
        }
    }