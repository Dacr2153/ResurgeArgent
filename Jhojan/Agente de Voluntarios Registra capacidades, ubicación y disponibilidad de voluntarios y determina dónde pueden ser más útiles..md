# Agente de Voluntarios Registra capacidades, ubicación y disponibilidad de voluntarios y determina dónde pueden ser más útiles.

El Agente de Voluntarios tiene como rol principal la ingesta de datos de voluntarios, el registro de sus capacidades, ubicación y disponibilidad, y la determinación dinámica de su asignación óptima a tareas específicas de búsqueda y rescate (**S1-S5**) y primeros auxilios (**T1-T3**). Esto se realiza en coordinación con las unidades de rescate oficiales y el Centro de Manejo de Desastres (**DMC**), optimizando el uso de recursos humanos bajo condiciones de incertidumbre y previniendo la aglomeración desorganizada en las zonas de desastre.

A continuación, se detalla la propuesta técnica, metodológica y operativa para la implementación del **Agente de Voluntarios**, estructurada bajo tus requerimientos y completamente respaldada por la evidencia científica y operativa de tus fuentes

**Rol Principal:** Registrar perfiles, capacidades y ubicación de voluntarios para asignarlos dinámicamente y de forma síncrona a las tareas más críticas (búsqueda, rescate y triaje de heridos), minimizando la demanda de ayuda insatisfecha y controlando el comportamiento de abandono y las restricciones de transporte en la zona de desastre

## 1. Interfaz y Datos de Entrada
Los datos capturados por la interfaz del agente provienen de dos flujos de información integrados (el registro de voluntarios y los reportes de incidentes en tiempo real):

- **Datos del Perfil del Voluntario:**
    - **Identificación y Ubicación:** Coordenadas de origen o región geográfica actual ($b \in B$).
    - **Disponibilidad Temporal:** Horas máximas permitidas de labor en cada periodo de respuesta ($Vmax_p$) para prevenir el agotamiento.
    - **Profesión / Nivel de Capacitación (**$w \in W_1$**):** Clasificación según las cuatro categorías operativas inspiradas en programas oficiales:
        1. _Search and Rescue Volunteer_ (Voluntario de Búsqueda y Rescate - Profesión 2).
        2. _Professional Healthcare Volunteer_ (Personal Médico Voluntario - Profesión 5/6).
        3. _First Aid Volunteer_ (Voluntario de Primeros Auxilios - Profesión 7).
        4. _Spontaneous Volunteer / Support Staff_ (Voluntario Espontáneo / Apoyo - Profesión 8).
    - **Estado de Retención:** Tasa esperada de abandono voluntario ($V_q$) para modelar de forma realista la pérdida de personal en periodos futuros ($p \in 2..P$).
- **Datos de Requerimiento de la Tarea (Procedentes del RAG / SOP):**
    - Demanda de trabajo en horas-hombre ($D^s_{wpb}$) calculada según el volumen de damnificados en la zona.
    - Clasificación de víctimas según el triaje estándar de la OTAN: mínimas, retrasadas o inmediatas.
    - Rutas y tiempos de viaje estimados ($ttime_{bb'}$) afectados por fallas o bloqueos viales por escenario ($f^s_{bb'}$).

---


## 2. Arquitectura del Agente (Componentes Integrados)

El agente está diseñado con una arquitectura modular desacoplada inspirada en el ecosistema **ResQConnect** y el modelo de optimización de **Kapukaya & Satoğlu**:

- **Módulo de Ingesta y Extracción (Meta Node):** Emplea un modelo de lenguaje para normalizar las solicitudes de los ciudadanos y los registros de voluntarios, infiriendo de manera estructurada su ubicación, nivel de entrenamiento y urgencia del entorno.
- **Módulo de Recuperación Filtrada (Filtered Retriever Node):** Conecta las habilidades del voluntario con la base de conocimientos interna de directrices de la esfera (_Sphere Guidelines_), manuales de INSARAG y procedimientos operativos estándar (SOP) locales del desastre
- **Motor de Optimización Matemática (AUGMECON Solver):** Resuelve el modelo estocástico de dos etapas para calcular las asignaciones de voluntarios que minimizan la demanda de personal insatisfecha ($Z_1$), reduciendo simultáneamente los costos de transferencia interregional ($Z_2$).
- **Evaluador de Seguridad y Adecuación (Assessor Node):** Valida de forma determinista que no se envíe a voluntarios de bajo entrenamiento a zonas de alto riesgo (como rescate estructural en escombros $S2$) sin la presencia y dirección física de unidades de rescate profesionales ($RU$).

## 3. Flujo de Trabajo Paso a Paso (Workflow Integrado)

El flujo operativo del agente se ejecuta de manera determinista para asegurar su confiabilidad en situaciones extremas35:

1. **Registro y Clasificación:** El voluntario ingresa su perfil en la aplicación. El **Meta Node** extrae sus capacidades y genera una entrada estructurada.
2. **Identificación de Tareas Disponibles:** El sistema calcula las demandas de trabajo ($D^s_{wpb}$) basándose en los reportes de víctimas y las duraciones de las tareas según el escenario activo ($durat^s_t$).
3. **Filtrado por Reglas de Seguridad (SOP):** El **Assessor Node** evalúa el emparejamiento voluntario-tarea. Si un voluntario espontáneo (Profesión 8) es pre-asignado a una tarea de alta complejidad, el sistema lo reubica automáticamente a tareas de apoyo (como traslado seguro o distribución).
4. **Cálculo de la Asignación Óptima:** Se corre el optimizador matemático para programar las asignaciones del periodo actual y los traslados interregionales de periodos futuros, restando el retraso vial provocado por el desastre y aplicando el límite de aglomeración ($Rat_v$) para prevenir congestión innecesaria en la zona crítica.
5. **Validación de Recursos Simultáneos:** El sistema asegura la asignación simultánea de personal y equipamiento5. Por ejemplo, no se asignarán paramédicos o médicos voluntarios a primeros auxilios ($T2$ o $T3$) si no se cuenta con ambulancias o kits médicos disponibles en la región ($b$) en ese instante.
6. **Despacho y Reoptimización Adaptativa (AET Policy):** Si surge un nuevo incidente crítico o se registra una gran oleada de voluntarios, el motor de eventos calcula el puntaje de disrupción ($D(t)$). Si supera el umbral adaptativo ($\Theta(t)$), se ejecuta una reoptimización global; de lo contrario, se procesa mediante una asignación local rápida para no alterar las rutas ya comprometidas.
## 4. Esquema de Datos de Salida (Output Schema - JSON Unificado)

El agente emite sus recomendaciones de asignación en un formato estructurado e interoperable para consumo del panel de control del DMC:

```
{
  "timestamp": "2026-08-28T09:58:45-07:00",
  "disaster_metadata": {
    "disaster_type": "earthquake",
    "detected_severity_scenario": "S19",
    "active_period": 1,
    "district_id": "Kartal_District_1"
  },
  "volunteer_capacity_summary": {
    "registered_volunteers_total": 150,
    "expected_quitting_rate": 0.15,
    "active_work_hours_capacity": 1800.0
  },
  "allocations": [
    {
      "allocation_id": "VOL-ALLOC-001",
      "region_id": "Region_19",
      "profession_id": 2,
      "profession_name": "Search and Rescue Volunteer",
      "assigned_man_hours": 950.0,
      "unmet_demand_remaining": 207.0,
      "assigned_tasks": [
        {
          "task_code": "S2",
          "task_name": "Rescue from Debris",
          "priority": "High",
          "supervised_by_rescue_unit": true
        }
      ]
    },
    {
      "allocation_id": "VOL-ALLOC-002",
      "region_id": "Region_14",
      "profession_id": 8,
      "profession_name": "Spontaneous Volunteer (Support Staff)",
      "assigned_man_hours": 775.0,
      "unmet_demand_remaining": 0.0,
      "assigned_tasks": [
        {
          "task_code": "S3",
          "task_name": "Dispatch to Safe Zone",
          "priority": "Medium",
          "supervised_by_rescue_unit": false
        }
      ]
    }
  ],
  "interregional_transfers": [
    {
      "transfer_id": "TR-VOL-08",
      "profession_id": 8,
      "origin_region": "Region_1",
      "destination_region": "Region_16",
      "transferred_volunteers_count": 12,
      "total_transferred_hours": 94.0,
      "estimated_travel_delay_minutes": 25.4
    }
  ],
  "resource_synchronization": {
    "ambulances_assigned": 5,
    "medical_kits_assigned": 410,
    "simultaneous_assignment_validated": true
  },
  "governance": {
    "human_in_the_loop_approval_required": true,
    "safety_checks_passed": true
  }
}
```




## 5. Prompt Maestro del Agente 1 - A1-RCE (System Prompt)
Este prompt define el comportamiento central y las restricciones lógicas y éticas que el LLM del agente debe acatar:

# ROLE AND GOAL
You are the Volunteer Coordination and Allocation Agent (A1-RCE), an expert decision-support entity in disaster logistics. Your primary goal is to map volunteer profiles, locations, and skills to field-ready tasks during critical emergencies, strictly adhering to Standard Operating Procedures (SOPs), INSARAG standards, and mathematical dynamic allocation guidelines.

# OPERATIONAL CONSTRAINTS (MANDATORY CITED RULES)
1. VOLUNTEER CATEGORIES: Classify and assign volunteers strictly to one of the following four roles:
   - Profession 2: Search and Rescue Volunteer
   - Profession 5/6: Professional Healthcare Volunteer
   - Profession 7: First Aid Volunteer
   - Profession 8: Spontaneous Volunteer (Support Staff)
2. SAFETY FIRST: Spontaneous Volunteers (Profession 8) must NEVER be assigned to high-risk debris rescue (S2) or hazardous environments without direct coordination and supervision by government-appointed rescue units.
3. SIMULTANEOUS ALLOCATION: Volunteers performing medical treatment or transport (T1-T3) must be paired synchronously with the required renewable resources (Ambulances) and non-renewable resources (Medical Kits). No medical tasks should be assigned if the necessary materials are unavailable.
4. PLAN STABILITY: Limit plan "nervousness." Do not suggest re-routing volunteers mid-transit unless an extreme event of higher urgency class is identified.
5. NO HUMAN REPLACEMENT: Treat all generated outputs as "recommendations" subject to approval by the central Disaster Management Center (DMC).

# CONSTRAINED OUTPUT SCHEMA
Your output must be structured strictly in valid JSON according to the unified output schema provided. Do not include conversational preambles, introductory sentences, or markdown notes outside of the JSON. If parameters are missing, output the appropriate warning flags in the metadata block and request human validation.
---

6. Stack Tecnológico de Implementación Recomendado

Para asegurar un funcionamiento robusto y continuo en infraestructuras de red inestables o saturadas:

- **Modelos de Lenguaje (LLM):**
    - _Cloud/Orquestador Central:_ **GPT-4o** o **Qwen2.5-72B-Instruct** para el procesamiento completo de RAG en el centro de mando.
    - _Edge/Dispositivo Móvil:_ **Qwen2.5-0.5B** cuantizado a 4 bits en formato de ejecución nativo `.task` de Google MediaPipe, garantizando respuestas interactivas locales menores a 500 ms sin conectividad móvil.
- **Framework de Orquestación y Observabilidad:**
    - **Langfuse:** Para auditar latencias, rastrear el consumo de tokens de los agentes e inspeccionar cada paso de la asignación.
    - **Tavily API:** Como bypass de búsqueda web cuando la base interna de SOP no cubra la especificidad del reporte ciudadano.
- **Base de Datos Vectorial:**
    - **Chroma Vector DB** para almacenar guías indexadas por tipo de riesgo (inundaciones y deslizamientos de tierra), sincronizada con una base relacional **PostgreSQL + PostGIS** para consultas de proximidad espacial y mapeo de rutas de ambulancias.
- **Motor de Optimización Matemática:**
    - **IBM CPLEX Optimization Studio** o solver open-source **CBC** (vía Python-PuLP) para resolver el modelo estocástico de asignación en el servidor central.

## 6. Stack Tecnológico de Implementación Recomendado

Para asegurar un funcionamiento robusto y continuo en infraestructuras de red inestables o saturadas:

- **Modelos de Lenguaje (LLM):**
    - _Cloud/Orquestador Central:_ **GPT-4o** o **Qwen2.5-72B-Instruct** para el procesamiento completo de RAG en el centro de mando.
    - _Edge/Dispositivo Móvil:_ **Qwen2.5-0.5B** cuantizado a 4 bits en formato de ejecución nativo `.task` de Google MediaPipe, garantizando respuestas interactivas locales menores a 500 ms sin conectividad móvil.
- **Framework de Orquestación y Observabilidad:**
    - **Langfuse:** Para auditar latencias, rastrear el consumo de tokens de los agentes e inspeccionar cada paso de la asignación.
    - **Tavily API:** Como bypass de búsqueda web cuando la base interna de SOP no cubra la especificidad del reporte ciudadano.
- **Base de Datos Vectorial:**
    - **Chroma Vector DB** para almacenar guías indexadas por tipo de riesgo (inundaciones y deslizamientos de tierra), sincronizada con una base relacional **PostgreSQL + PostGIS** para consultas de proximidad espacial y mapeo de rutas de ambulancias.
- **Motor de Optimización Matemática:**
    - **IBM CPLEX Optimization Studio** o solver open-source **CBC** (vía Python-PuLP) para resolver el modelo estocástico de asignación en el servidor central.

## 7. Características de Seguridad, Trazabilidad y Calidad
Para proteger la integridad de los voluntarios y asegurar la calidad de las decisiones:

- **Trazabilidad de la Evidencia (No-Alucinación):** Cada tarea asignada por el agente para búsqueda o primeros auxilios incluye un marcador de origen que apunta al fragmento específico del SOP o directriz de INSARAG que sustenta dicha recomendación, brindando transparencia absoluta a los operadores de emergencia.
- **Protección ante Fatiga:** El sistema evalúa proactivamente las horas máximas de trabajo ($Vmax_p$) restando el tiempo de traslado terrestre en las carreteras congestionadas o dañadas ($ttime_{bb'} \cdot (1 + f^s_{bb'})$) para asegurar relevos justos y seguros.
- **Gobernanza Human-in-the-Loop (HITL):** El agente está diseñado como una herramienta de soporte que asiste a los tomadores de decisiones; el sistema requiere la aprobación manual de un operador humano en el panel de control del DMC antes de enviar cualquier orden de despacho o transferencia a los teléfonos de los voluntarios.
- **Protección contra Aglomeraciones (Aglomeration Shield):** Se controlan los ingresos desordenados de voluntarios espontáneos mediante la restricción del multiplicador de seguridad ($Rat_v$), evitando la formación de multitudes inconscientes que dificulten las labores de las unidades profesionales.


## 8. Flujo de Datos: De Entrada a Salida

El ciclo completo del dato se despliega de la siguiente manera:

```
[ Voluntario registra perfil / DMC detecta incidentes (Entradas) ]
                           │
                           ▼
     [ Meta Node: Extracción de metadatos y perfilado ]
                           │
                           ▼
 [ Filtered Retriever: Filtrado semántico en ChromaDB por tipo de peligro ]
                           │
                           ▼
 [ Assessor Node: Evaluación de suficiencia y seguridad (¿SOP aplicable?) ]
         ├── (Inadecuado) ──> [ Reformulator Node: Refinamiento de consulta ]
         └── (Adecuado) ───> [ Task Generator: Creación de requerimientos ]
                           │
                           ▼
 [ Solver de AUGMECON2: Optimización estocástica multiperiodo de asignación ]
                           │
                           ▼
 [ AET Trigger Engine: Evaluación de reoptimización global vs. inserción local ]
                           │
                           ▼
[ Despacho aprobado por DMC / Guías offline cargadas en dispositivo móvil (Salidas) ]
```

Este diseño integra de manera armoniosa la precisión del modelado matemático de recursos de desastres con la flexibilidad operativa de los sistemas modernos de inteligencia artificial generativa.