from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date

class ProductoBase(BaseModel):
    nombre: str
    codigo_barras: Optional[str] = None
    costo: float = 0.0
    precio: float
    stock: int
    fecha_vencimiento: Optional[date] = None

class ProductoCreate(ProductoBase):
    pass

class ProductoResponse(ProductoBase):
    id: int
    class Config:
        from_attributes = True

class DetalleVentaCreate(BaseModel):
    producto_id: int
    cantidad: int

class VentaCreate(BaseModel):
    items: List[DetalleVentaCreate]

# Esquemas para la Caja
class AbrirCaja(BaseModel):
    monto_inicial: float

class CerrarCaja(BaseModel):
    monto_final: float

class CajaResponse(BaseModel):
    id: int
    fecha_apertura: datetime
    fecha_cierre: Optional[datetime] = None
    monto_inicial: float
    monto_final: Optional[float] = None
    estado: str

    class Config:
        from_attributes = True