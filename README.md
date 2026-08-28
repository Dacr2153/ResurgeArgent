El Sistema de Coordinación de Respuesta es una herramienta inteligente diseñada para 
apoyar la gestión integral de emergencias y desastres, convirtiendo información dispersa,
cambiante y proveniente de múltiples fuentes —ciudadanos, personas afectadas, voluntarios,
organizaciones, autoridades y sistemas geográficos— en información estructurada y 
decisiones accionables. Mediante una arquitectura multiagente, el sistema puede 
identificar necesidades, riesgos, recursos disponibles, concentración de personas, 
vías bloqueadas y zonas que requieren atención, permitiendo coordinar de manera dinámica 
la asignación de personas, suministros, vehículos y servicios. Su objetivo es llevar el 
recurso correcto al lugar correcto en el momento correcto, evitando la duplicación de 
esfuerzos, la saturación de determinados puntos y la distribución ineficiente de recursos.

Además de la atención inmediata, el sistema incorpora una dimensión de recuperación, 
reconstrucción y reactivación económica, mediante agentes especializados que orienten a 
personas, empresas y microempresas afectadas según su situación particular. Estos 
agentes pueden analizar las condiciones reportadas por cada usuario y proporcionar 
orientación sobre trámites, ayudas disponibles, procesos de recuperación, documentación 
requerida, alternativas de financiación, seguros, obligaciones y rutas institucionales, 
siempre como asistencia informativa y de orientación, no como sustituto de un profesional
jurídico o financiero. De esta manera, la plataforma evoluciona desde un sistema de 
respuesta ante emergencias hacia un ecosistema inteligente de gestión de desastres, 
capaz de coordinar la atención inmediata y, posteriormente, apoyar la recuperación de 
las comunidades y la reactivación económica de las unidades productivas afectadas.

```
1. INGRESO DE INFORMACIÓN
        ↓
2. VERIFICACIÓN
        ↓
3. ANÁLISIS GEOGRÁFICO Y DE RIESGO
        ↓
4. IDENTIFICACIÓN DE NECESIDADES
        ↓
5. IDENTIFICACIÓN DE RECURSOS DISPONIBLES
        ↓
6. PRIORIZACIÓN
        ↓
7. MATCHING
Necesidad ↔ Persona ↔ Recurso ↔ Vehículo
        ↓
8. PLANIFICACIÓN DE RUTAS Y LOGÍSTICA
        ↓
9. ASIGNACIÓN Y EJECUCIÓN
        ↓
10. COMUNICACIÓN / ALERTAS
        ↓
11. SEGUIMIENTO Y VERIFICACIÓN


        ↓
12. ACTUALIZACIÓN DEL ESTADO
        ↓
   ┌────┴────┐
   ↓         ↓
¿Emergencia  ¿Necesidad
continúa?    resuelta?
   ↓         ↓
  Sí        NO → nueva asignación
   ↓
   └──→ volver al análisis
             
             ↓
      RECUPERACIÓN
             ↓
  Jurídico + Ayudas + Reconstrucción
             ↓
      Reactivación económica
             ↓
       SEGUIMIENTO
             ↓
       RECUPERACIÓN

```

1. Agente Orquestador
Coordina a todos los agentes, consolida información y determina qué acciones deben ejecutarse y en qué orden.

## David:

2. Agente de Ingesta de Información
Recibe información de ciudadanos, afectados, voluntarios, organizaciones, autoridades, sensores, APIs y fuentes geográficas.

3. Agente de Verificación
Valida, contrasta y asigna un nivel de confianza a los reportes, evitando información falsa, duplicada o desactualizada.

4. Agente de Riesgos
Identifica y clasifica zonas de riesgo, estructuras afectadas, amenazas y posibles zonas peligrosas.(opcional)

5. Agente Geoespacial y Movilidad
Gestiona mapas, ubicación de personas, puntos de ayuda, zonas afectadas y distribución geográfica de recursos. Detecta vías bloqueadas, congestión, accesos restringidos y propone rutas alternativas.


## Jhojan: 

7. Agente de Necesidades
Identifica qué necesita cada zona: alimentos, agua, medicamentos, refugio, rescate, personal, transporte, etc.

8. Agente de Recursos
Controla disponibilidad y distribución de alimentos, agua, medicamentos, herramientas, vehículos, infraestructura y demás recursos.

9. Agente de Voluntarios
Registra capacidades, ubicación y disponibilidad de voluntarios y determina dónde pueden ser más útiles. - 
### 10. Agente de Matching/Asignación
Relaciona necesidades ↔ recursos ↔ empresas ↔ vehículos, buscando la asignación más eficiente.

        11. Agente Logístico
        Planifica el movimiento de recursos, personas y suministros desde su origen hasta el destino.- protocolos necesarios para presentar la ayuda. 

        12. Agente de Afectados
        Gestiona solicitudes de ayuda, registra empresas afectadas y hace seguimiento de sus necesidades. (Opcional)

        13. Agente de Puntos de Ayuda
        Administra refugios, centros de distribución, centros de acopio y demás puntos de atención, incluyendo su capacidad y nivel de saturación.

        14. Agente de Comunicación y Alertas
        Envía instrucciones, alertas, recomendaciones y actualizaciones a ciudadanos, voluntarios, organizaciones y coordinadores.

        15. Agente de Seguimiento
        Verifica si una necesidad fue atendida y actualiza el estado de cada operación.

Agentes para recuperación y reconstrucción - 2 etapa


16. Agente Jurídico/Orientación Legal
Orienta sobre trámites, derechos, documentación, obligaciones, ayudas y rutas institucionales según la situación del afectado.

17. Agente de Ayudas y Beneficios
Identifica programas gubernamentales, subsidios, ayudas, convocatorias y mecanismos de apoyo aplicables.

18. Agente de Reconstrucción
Apoya la identificación de necesidades de reparación o reconstrucción de viviendas, infraestructura y establecimientos.

19. Agente de Reactivación Económica
Analiza la situación de empresas y microempresas afectadas y recomienda rutas para su recuperación y continuidad.

20. Agente Financiero
Orienta sobre financiación, seguros, créditos, flujo de caja y alternativas de recuperación económica, sin reemplazar asesoría profesional.



