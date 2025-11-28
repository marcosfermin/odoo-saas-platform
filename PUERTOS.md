# Mapeo de Puertos - Odoo SaaS Platform

## Puertos Principales de la Aplicación

### Servicios Web
- **Odoo Web Interface**: `http://localhost:18069`
- **Odoo Longpolling**: `http://localhost:18072`
- **Odoo Tenant API**: `http://localhost:18080`
- **Admin Dashboard**: `http://localhost:15000`
- **Customer Portal**: `http://localhost:15001`
- **Nginx HTTP**: `http://localhost:10080`
- **Nginx HTTPS**: `https://localhost:10443`

### Bases de Datos y Caché
- **PostgreSQL**: `localhost:15432`
- **Redis**: `localhost:16379`

### Monitoreo y Métricas
- **Grafana Dashboard**: `http://localhost:13000`
  - Usuario por defecto: admin
  - Contraseña: Configurada en `.env` (GRAFANA_ADMIN_PASSWORD)

- **Prometheus**: `http://localhost:19094`
- **AlertManager**: `http://localhost:19095`

### Exportadores de Métricas
- **Admin Metrics**: `http://localhost:19090`
- **Portal Metrics**: `http://localhost:19091`
- **Worker Metrics**: `http://localhost:19092`
- **Backup Service Metrics**: `http://localhost:19093`
- **Odoo Metrics**: `http://localhost:18071`
- **Node Exporter**: `http://localhost:19100`
- **PostgreSQL Exporter**: `http://localhost:19187`
- **Redis Exporter**: `http://localhost:19121`
- **cAdvisor**: `http://localhost:18081`

## Resumen de Cambios

Todos los puertos han sido modificados para evitar conflictos con servicios locales:

| Servicio | Puerto Original | Puerto Nuevo |
|----------|----------------|--------------|
| PostgreSQL | 5432 | 15432 |
| Redis | 6379 | 16379 |
| Admin Dashboard | 5000 | 15000 |
| Portal | 5001 | 15001 |
| Odoo Web | 8069 | 18069 |
| Odoo Longpolling | 8072 | 18072 |
| Odoo Tenant API | 8080 | 18080 |
| Odoo Metrics | 8071 | 18071 |
| Nginx HTTP | 80 | 10080 |
| Nginx HTTPS | 443 | 10443 |
| Grafana | 3000 | 13000 |
| Prometheus | 9090 | 19094 |
| AlertManager | 9093 | 19095 |
| Node Exporter | 9100 | 19100 |
| PostgreSQL Exporter | 9187 | 19187 |
| Redis Exporter | 9121 | 19121 |
| cAdvisor | 8080 | 18081 |

## Cómo Acceder a los Servicios

### Acceso Principal
1. **Portal de Clientes**: `http://localhost:15001`
2. **Panel de Administración**: `http://localhost:15000`
3. **Odoo**: `http://localhost:18069`

### Monitoreo
1. **Grafana** (Visualización): `http://localhost:13000`
2. **Prometheus** (Métricas): `http://localhost:19094`

### Base de Datos (Solo para desarrollo/debugging)
```bash
# Conectar a PostgreSQL
psql -h localhost -p 15432 -U odoo -d odoo_saas

# Conectar a Redis
redis-cli -h localhost -p 16379
```

## Notas
- Todos los puertos están vinculados a `127.0.0.1` excepto los servicios principales de Odoo
- Los puertos de métricas están en el rango 19000-19200 para fácil identificación
- Los servicios web principales usan puertos en el rango 15000-18000
