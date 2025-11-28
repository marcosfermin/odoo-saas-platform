# 🔐 Credenciales y Acceso a las Plataformas

## 📋 Configuración Inicial Requerida

Antes de iniciar los servicios, **DEBES** crear un archivo `.env` basado en `.env.example`:

```bash
cp .env.example .env
```

Luego edita el archivo `.env` y configura las siguientes credenciales OBLIGATORIAS:

```env
# Credenciales de PostgreSQL
POSTGRES_USER=odoo
POSTGRES_PASSWORD=TuPasswordSeguroPostgres123!

# Credenciales de Redis
REDIS_PASSWORD=TuPasswordSeguroRedis123!

# Claves secretas (genera con: openssl rand -hex 32)
JWT_SECRET_KEY=tu_clave_secreta_jwt_32_caracteres_hex
FLASK_SECRET_KEY=tu_clave_secreta_flask_32_caracteres_hex

# Odoo Master Password
ODOO_MASTER_PASSWORD=TuPasswordMasterOdoo123!

# Grafana
GRAFANA_ADMIN_PASSWORD=TuPasswordGrafana123!
```

---

## 🌐 URLs de Acceso y Credenciales

### 1. **Grafana** - Monitoreo y Métricas
- **URL**: http://localhost:13000
- **Usuario**: `admin`
- **Contraseña**: El valor configurado en `GRAFANA_ADMIN_PASSWORD` en tu archivo `.env`
- **Descripción**: Dashboard de monitoreo con métricas de todos los servicios

---

### 2. **Admin Dashboard** - Panel de Administración
- **URL**: http://localhost:15000
- **Credenciales**: Se crean en el primer inicio
- **Proceso de registro**:
  1. Accede a http://localhost:15000
  2. Crea tu cuenta de administrador
  3. Las credenciales se almacenan en PostgreSQL
- **Descripción**: Panel para gestionar tenants, usuarios, subscripciones y configuración general

---

### 3. **Portal de Clientes** - Portal SaaS
- **URL**: http://localhost:15001
- **Credenciales**: Registro de clientes
- **Proceso**:
  1. Los clientes se registran desde http://localhost:15001
  2. Crean su cuenta y tenant
  3. Acceden a su instancia de Odoo
- **Descripción**: Portal donde los clientes gestionan sus subscripciones y acceden a Odoo

---

### 4. **Odoo Multi-Tenant** - Instancias de Odoo
- **URL**: http://localhost:18069
- **Master Password**: El valor configurado en `ODOO_MASTER_PASSWORD` en `.env`
- **Credenciales por Tenant**:
  - Cada tenant tiene su propia base de datos
  - El administrador del tenant crea sus credenciales durante la configuración
  - El acceso se gestiona mediante subdominios o parámetros de tenant
- **Descripción**: Servicio principal de Odoo con soporte multi-tenant

---

### 5. **PostgreSQL** - Base de Datos
- **Host**: `localhost`
- **Puerto**: `15432`
- **Usuario**: El valor en `POSTGRES_USER` (por defecto: `odoo`)
- **Contraseña**: El valor configurado en `POSTGRES_PASSWORD` en `.env`
- **Base de datos**: `odoo_saas` (nombre configurado en `POSTGRES_DB`)

**Conexión desde línea de comandos**:
```bash
psql -h localhost -p 15432 -U odoo -d odoo_saas
```

**Conexión desde DBeaver/pgAdmin**:
- Host: localhost
- Port: 15432
- Database: odoo_saas
- Username: odoo
- Password: [Tu POSTGRES_PASSWORD]

---

### 6. **Redis** - Cache y Sesiones
- **Host**: `localhost`
- **Puerto**: `16379`
- **Contraseña**: El valor configurado en `REDIS_PASSWORD` en `.env`

**Conexión desde redis-cli**:
```bash
redis-cli -h localhost -p 16379 -a TuPasswordRedis
```

---

### 7. **Prometheus** - Métricas
- **URL**: http://localhost:19094
- **Credenciales**: No requiere autenticación (solo localhost)
- **Descripción**: Sistema de monitoreo y alertas

---

### 8. **AlertManager** - Gestión de Alertas
- **URL**: http://localhost:19095
- **Credenciales**: No requiere autenticación (solo localhost)
- **Descripción**: Gestión de alertas de Prometheus

---

### 9. **cAdvisor** - Métricas de Contenedores
- **URL**: http://localhost:18081
- **Credenciales**: No requiere autenticación (solo localhost)
- **Descripción**: Monitoreo de recursos de contenedores

---

## 🔧 Endpoints de Métricas

Todos estos endpoints están disponibles en localhost y no requieren autenticación:

| Servicio | Puerto | URL |
|----------|--------|-----|
| Admin Metrics | 19090 | http://localhost:19090/metrics |
| Portal Metrics | 19091 | http://localhost:19091/metrics |
| Worker Metrics | 19092 | http://localhost:19092/metrics |
| Backup Metrics | 19093 | http://localhost:19093/metrics |
| Node Exporter | 19100 | http://localhost:19100/metrics |
| Redis Exporter | 19121 | http://localhost:19121/metrics |
| PostgreSQL Exporter | 19187 | http://localhost:19187/metrics |

---

## 🚀 Pasos para Iniciar

### 1. Generar Claves Secretas

```bash
# Generar JWT_SECRET_KEY
openssl rand -hex 32

# Generar FLASK_SECRET_KEY
openssl rand -hex 32
```

### 2. Configurar el archivo .env

```bash
cp .env.example .env
# Edita .env con tus credenciales
```

### 3. Iniciar los Servicios

```bash
podman compose -f docker-compose.complete.yml up -d --build
```

### 4. Verificar que los Servicios Están Corriendo

```bash
podman compose -f docker-compose.complete.yml ps
```

### 5. Acceder a las Plataformas

1. **Grafana**: http://localhost:13000 (admin / tu_password_grafana)
2. **Admin Dashboard**: http://localhost:15000 (crear cuenta)
3. **Portal**: http://localhost:15001 (registro de clientes)
4. **Odoo**: http://localhost:18069

---

## 🔒 Recomendaciones de Seguridad

1. **Nunca uses las contraseñas de ejemplo** - Cámbialas todas
2. **Genera claves secretas fuertes** - Usa `openssl rand -hex 32`
3. **No compartas el archivo .env** - Está en .gitignore por seguridad
4. **Usa contraseñas únicas** - Cada servicio debe tener una contraseña diferente
5. **Backup regular** - Las credenciales se almacenan en PostgreSQL

---

## 📝 Variables de Entorno Críticas

```env
# Base de Datos
POSTGRES_USER=odoo
POSTGRES_PASSWORD=<PASSWORD_FUERTE>
POSTGRES_DB=odoo_saas

# Redis
REDIS_PASSWORD=<PASSWORD_FUERTE>

# Seguridad
JWT_SECRET_KEY=<32_CARACTERES_HEX>
FLASK_SECRET_KEY=<32_CARACTERES_HEX>

# Odoo
ODOO_MASTER_PASSWORD=<PASSWORD_FUERTE>

# Monitoreo
GRAFANA_ADMIN_PASSWORD=<PASSWORD_FUERTE>
```

---

## 🆘 Solución de Problemas

### No puedo acceder a los servicios

1. Verifica que los contenedores están corriendo:
   ```bash
   podman compose -f docker-compose.complete.yml ps
   ```

2. Revisa los logs de servicios específicos:
   ```bash
   podman compose -f docker-compose.complete.yml logs admin
   podman compose -f docker-compose.complete.yml logs odoo-service
   ```

### Error de autenticación en PostgreSQL

- Verifica que `POSTGRES_PASSWORD` en `.env` coincide con lo que usas para conectar
- Revisa que el usuario es `odoo` (o el valor en `POSTGRES_USER`)

### Error de autenticación en Redis

- Verifica que `REDIS_PASSWORD` está correctamente configurado
- Usa el mismo password al conectar con redis-cli

---

## 📚 Documentación Adicional

- **Puertos**: Ver `PUERTOS.md` para mapeo completo de puertos
- **Arquitectura**: Ver `README.md` para detalles de arquitectura
- **Configuración**: Ver `.env.example` para todas las opciones disponibles
