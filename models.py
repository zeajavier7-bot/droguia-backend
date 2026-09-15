from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    codigo_barras = Column(String, unique=True, index=True)
    costo = Column(Float, default=0.0)
    precio = Column(Float)
    stock = Column(Integer, default=0)

class Venta(Base):
    __tablename__ = "ventas"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime, default=datetime.utcnow)
    total_venta = Column(Float, default=0.0)
    total_costo = Column(Float, default=0.0)
    ganancia_total = Column(Float, default=0.0)

    detalles = relationship("DetalleVenta", back_populates="venta")

class DetalleVenta(Base):
    __tablename__ = "detalles_venta"

    id = Column(Integer, primary_key=True, index=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"))
    producto_id = Column(Integer, ForeignKey("productos.id"))
    cantidad = Column(Integer)
    precio_unitario = Column(Float)
    costo_unitario = Column(Float)

    venta = relationship("Venta", back_populates="detalles")
    producto = relationship("Producto")

class Caja(Base):
    __tablename__ = "cajas"

    id = Column(Integer, primary_key=True, index=True)
    fecha_apertura = Column(DateTime, default=datetime.utcnow)
    fecha_cierre = Column(DateTime, nullable=True)
    monto_inicial = Column(Float, default=0.0)
    monto_final = Column(Float, nullable=True)
    estado = Column(String, default="abierta")  # 'abierta' o 'cerrada'