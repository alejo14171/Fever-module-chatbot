# Casos de Prueba Organizados

## Casos Mapeados (10/15)

| ID | Edad Esperada | Temp Esperada | Archivo | Edad Real | Temp Real | Match |
|----|---------------|---------------|---------|-----------|-----------|-------|
| A1 | 2m | 38.0°C | A1_edad2m_temp38.0.json | 2m | 38.0°C | ✅ Perfecto |
| A2 | 12m (1año) | 37.5°C | A2_edad12m_temp37.5.json | 12m | 37.5°C | ✅ Perfecto |
| A3 | 4m | 39.5°C | A3_edad4m_temp40.0.json | 4m | 40.0°C | ⚠️ Temp +0.5°C |
| A4 | 24m (2años) | 38.1°C | A4_edad10m_temp38.0.json | 10m | 38.0°C | ⚠️ Edad -14m |
| A5 | 60m (5años) | 37.0°C | A5_edad48m_temp37.5.json | 48m | 37.5°C | ⚠️ Edad -12m, Temp +0.5°C |
| B1 | 4m | 40.0°C | B1_edad4m_temp38.2.json | 4m | 38.2°C | ⚠️ Temp -1.8°C |
| B3 | 1m | 37.8°C | B3_edad2m_temp38.0.json | 2m | 38.0°C | ⚠️ Edad +1m |
| B4 | 84m (7años) | 38.5°C | B4_edad72m_temp40.0.json | 72m | 40.0°C | ⚠️ Edad -12m, Temp +1.5°C |
| C1 | 9m | 41.0°C | C1_edad4m_temp38.0.json | 4m | 38.0°C | ⚠️ Edad -5m, Temp -3°C |
| D1 | 2m | 38.8°C | D1_edad2m_temp39.0.json | 2m | 39.0°C | ✅ Temp +0.2°C |

## Casos Faltantes (5/15)

- **B2**: 36m (3años), 36.5°C
- **C2**: 72m (6años), 37.2°C
- **C3**: 120m (10años), 36.8°C
- **D2**: 96m (8años), 37.4°C
- **D3**: 132m (11años), 38.0°C

## Notas

- Los archivos están organizados en esta carpeta con el formato: `{CASE_ID}_edad{age}m_temp{temp}.json`
- Los casos marcados con ⚠️ tienen diferencias menores pero son los mejores matches disponibles
- Para obtener casos más exactos, se necesitarían más conversaciones de prueba
