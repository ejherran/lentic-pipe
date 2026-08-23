# Guía completa para ejecutar `Closure V2` con GPT‑Codex — inteligencia media

**Proyecto:** `ejherran/lentic-pipe`
**Propósito:** completar de forma científicamente defendible el ajuste y la evaluación de las ramas temporales P0/P1, generar comparaciones estimables y dejar en el repositorio toda la evidencia necesaria para actualizar la tesis.
**Tipo de documento:** runbook operativo y protocolo computacional interno.
**Fecha de diseño:** 22 de agosto de 2026, zona horaria `America/Bogota`.
**Estado precedente que debe preservarse:** `Closure V1`, tag anotado `thesis-closure-v1`.

---

## 1. Resumen ejecutivo

`Closure V2` no debe modificar, corregir ni reinterpretar retroactivamente `Closure V1`. Debe abrir un experimento nuevo, con namespace, protocolo, artefactos, commits, tags, logs y límites de afirmación propios.

La razón técnica de V2 es concreta. En `Closure V1`, P0 y P1 dispusieron de:

- 9.413 orígenes de ajuste en `training + model_selection`;
- 8.925 secuencias completas;
- 488 secuencias con `autoregressive_target_unavailable`;
- 94,82 % de disponibilidad para ajuste.

La política V1 exigía que **todas** las filas de ajuste fueran `success`. Por eso el ajuste no se intentó y ambos modelos quedaron `model_unavailable`, aunque la gran mayoría de las secuencias era utilizable.

`Closure V2` sustituirá esa regla por una política preespecificada de **elegibilidad por casos completos**, con estas propiedades:

1. Las secuencias completas se usan para ajustar el modelo.
2. Las secuencias incompletas permanecen en el ledger de disponibilidad y nunca se eliminan silenciosamente.
3. P0 y P1 usan la misma política.
4. La comparación primaria P0–P1 usa una intersección exacta de claves de ajuste.
5. Los resultados se reportan con denominadores `intent-to-predict`, elegibilidad, éxito y `shared-success`.
6. Se analiza si la exclusión por incompletitud introduce sesgo.
7. El holdout ya abierto de V1 sólo puede usarse como evaluación retrospectiva complementaria.
8. Una afirmación confirmatoria nueva exige una superficie de evaluación fresca, bloqueada después del model lock de V2.
9. P1 puede resultar superior, competitivo, equivalente en la muestra, inferior o nuevamente no evaluable. Ningún resultado se presupone.

La ganancia garantizada de V2 es convertir una comparación bloqueada en una comparación técnicamente ejecutable y auditable. La mejora de las métricas es plausible, pero no está garantizada.

---

## 2. Autoridades que deben verificarse antes de empezar

### 2.1 Autoridades Git de `Closure V1`

El operador debe comprobar, no asumir, estas identidades:

```text
Tag anotado de cierre:
thesis-closure-v1

Commit terminal de certificación:
eb07598aa54a0944d1a87fe46d62415d0a4454aa

Commit de resultados científicos:
ea8ddce7f8edb9a61db97e29178e52603fa371b1

Commit de síntesis R-SYN:
528dcb74a7c08b65f262901e4562a67b784db8c9

Commit editorial:
d1daa3059462854d6ddf5199fbc05515cec76982
```

Al redactar esta guía, `main` estaba en:

```text
e8f22ed733de56b6616b4ab9f651eb41bd095bb6
```

Ese valor es una referencia histórica, no una condición permanente. Al ejecutar V2 se debe registrar el `HEAD` real de entrada.

### 2.2 Fuentes documentales

Leer antes de editar:

```text
README.md
docs/closure_v1/ANALYSIS_PLAN.md
docs/closure_v1/PROTOCOL_AMENDMENT_V1_1.md
configs/closure_v1/analysis_plan.yaml
configs/closure_v1/model_benchmark.yaml
configs/closure_v1/development_runtime.yaml
reports/closure_v1/11_synthesis/FINAL_CLOSURE_REPORT.md
reports/closure_v1/11_synthesis/FINAL_CLOSURE_MATRIX.csv
reports/closure_v1/11_synthesis/THESIS_CLAIM_EVIDENCE_MATRIX.csv
reports/closure_v1/12_certification/FINAL_DOCTORAL_CERTIFICATION_REPORT.md
reports/closure_v1/12_certification/final_certification_manifest.json
```

Fuentes privadas o externas de contexto:

```text
CIERRE_FASES_1_2_3_4.md
SOLICITUD_MODIFICACION_PROTOCOLO_.docx
251110_Protocolo_Investigacion.pdf
RubricaDoctorado.pdf
```

### 2.3 Jerarquía de autoridad

En caso de contradicción:

1. tag y commits publicados;
2. manifests canónicos y locks;
3. tablas estructuradas CSV/JSON/YAML;
4. reportes Markdown;
5. notas privadas;
6. memoria humana.

Nunca elegir un número por conveniencia.

---

## 3. Decisiones científicas no negociables

### 3.1 Inmutabilidad de V1

Queda prohibido:

- mover o recrear `thesis-closure-v1`;
- modificar archivos bajo `configs/closure_v1/`, `docs/closure_v1/`, `reports/closure_v1/` o `data/closure_v1/` para “arreglar” el cierre;
- reemplazar los manifests P0/P1 V1;
- afirmar que P0/P1 V1 fueron entrenados;
- sobrescribir tablas, figuras o certificaciones V1;
- usar resultados V2 como si hubieran pertenecido a V1.

V2 debe ser aditivo.

### 3.2 Namespace exclusivo

Todo artefacto nuevo debe vivir en un namespace V2:

```text
configs/closure_v2/
docs/closure_v2/
data/closure_v2/
models/closure_v2/
reports/closure_v2/
src/experiments/closure_v2/
tests/closure_v2/
```

No crear variantes innecesarias como:

```text
*_final.py
*_final_v2.py
*_final_v2_fixed.py
*_final_v2_fixed_latest.py
```

Cada rol tendrá un único archivo canónico. Los cambios históricos quedan en Git.

### 3.3 Política de resultados

Un resultado puede ser:

```text
confirmatory_available
descriptive_available
posthoc_available
insufficient_support
model_unavailable
not_applicable
failed
```

No usar cero para representar ausencia de estimación.

### 3.4 Lenguaje metodológico

La implementación temporal debe llamarse:

```text
residual probabilistic GRU
GRU probabilística residual
modelo temporal probabilístico
```

No llamarla `GRU-D canónica` mientras no implemente explícitamente máscaras y decaimiento temporal del mecanismo GRU-D original.

### 3.5 P0 y P1

Definición:

| ID | Estado de entrada | Función |
|---|---|---|
| P0 | estado fuzzy experto sin Chl-a actual | comparador temporal experto |
| P1 | estado ANFIS adaptativo sin Chl-a actual | candidato temporal principal |

Ambos deben compartir:

- arquitectura;
- seeds;
- presupuesto de optimización;
- roles temporales;
- política de elegibilidad;
- criterios de parada;
- calibración;
- horizontes;
- superficie evaluativa;
- política de fallos.

### 3.6 Holdout V1

Las 88 ubicaciones V1 y sus outcomes ya fueron abiertos. Cualquier nueva ejecución sobre esa superficie se etiqueta:

```text
legacy_posthoc
retrospective_complementary
```

No se etiqueta:

```text
new_confirmatory
prospective
external_validation
```

---

## 4. Objetivo de `Closure V2`

### 4.1 Objetivo general

Ajustar y evaluar P0 y P1 mediante una política preespecificada de elegibilidad por casos completos, preservando todos los denominadores y fallos, y completar las comparaciones de desempeño, incertidumbre, degradación y planificación que dependían de P1.

### 4.2 Objetivos específicos

1. Crear un protocolo V2 independiente y versionado.
2. Reutilizar como inputs inmutables los estados y secuencias de desarrollo V1 cuando sus hashes y roles sean válidos.
3. Construir el ledger completo de elegibilidad.
4. Evaluar el sesgo de las 488 secuencias no elegibles.
5. Ajustar P0/P1 para cinco seeds, sin sustitución.
6. Seleccionar y calibrar modelos sólo con datos de desarrollo.
7. Bloquear modelos antes de abrir una superficie fresca.
8. Evaluar P1 frente a B2, P0, A0/A1 y M0 en superficies comunes.
9. Ejecutar inferencia agrupada por ubicación.
10. Completar degradación M0–P1.
11. Completar planificación basada en rollouts P1.
12. Generar un bundle de tesis y una certificación reproducible.

---

## 5. Diseño experimental de V2

## 5.1 Superficie primaria

Conservar la superficie estricta:

```text
closure_v2_wqp_adaptive_no_current_chla
```

Reglas:

- historia de 12 meses;
- horizontes de 1, 2 y 3 meses calendario;
- Chl-a observada y cualquier derivado de ella prohibidos en los inputs;
- estado de nueve canales:
  `yN`, `yF`, `yT`, `sigma_N`, `sigma_F`, `sigma_T`,
  `delta_yN`, `delta_yF`, `delta_yT`;
- origen y target dentro del mismo rol temporal para desarrollo;
- no refit en evaluación.

## 5.2 Roles temporales de desarrollo

Mantener, como primera opción, los roles V1:

```text
training:              hasta 2018-12
model_selection:       2019-01 a 2020-12
calibration_threshold: 2021-01 a 2021-12
```

Esto permite reutilizar evidencia development-only creada antes del unblinding V1 y evita entrenar con las 88 ubicaciones retenidas.

Si se decide ampliar el periodo de desarrollo, esa decisión debe constituir otro protocolo, no una modificación silenciosa de este runbook.

## 5.3 Política primaria de elegibilidad

Una fila es elegible para ajuste si cumple simultáneamente:

```text
assignment_role == development
time_role in {training, model_selection}
sequence_status == success
13 listas de entrada finitas
9 targets finitos
origen y target dentro del mismo rol temporal
sin Chl-a observada ni derivados
sin overlap con cualquier cohorte de evaluación
```

Las filas no elegibles:

- conservan identidad;
- conservan `failure_reason`;
- no contribuyen a la pérdida;
- aparecen en todos los manifiestos;
- no se sustituyen;
- no se convierten en filas cero.

### 5.3.1 Umbrales para autorizar el fit

La familia temporal se considera ajustable si:

```yaml
minimum_overall_fit_eligibility_fraction: 0.90
minimum_training_rows: 5000
minimum_model_selection_rows: 500
minimum_calibration_rows: 200
minimum_training_locations: 200
minimum_model_selection_locations: 50
minimum_calibration_locations: 30
```

Los conteos V1 conocidos —8.925 de 9.413 filas de fit— superan el umbral global. Codex debe recalcular todos los valores desde los artefactos, no copiar esta conclusión.

### 5.3.2 Intersección primaria P0/P1

Para la comparación principal, crear:

```text
shared_fit_keys =
keys(P0.sequence_status == success)
∩
keys(P1.sequence_status == success)
```

P0 y P1 se entrenan primariamente sobre la misma intersección.

Análisis secundarios admitidos:

```text
P0 model-specific complete cases
P1 model-specific complete cases
masked-loss sensitivity
```

Ninguno sustituye el análisis primario.

## 5.4 Análisis del sesgo de elegibilidad

Antes de entrenar, comparar secuencias elegibles y no elegibles por:

- rol temporal;
- año y mes;
- ubicación;
- estación climática;
- cobertura de variables;
- número de canales faltantes;
- `yN`, `yF`, `yT`;
- incertidumbres del estado;
- deltas;
- variables de calidad;
- frecuencia histórica de bloom dentro de desarrollo;
- proporción de filas no elegibles por sitio.

Generar:

```text
eligibility_counts.csv
eligibility_by_role.csv
eligibility_by_location.csv
eligibility_by_month.csv
eligibility_covariate_balance.csv
eligibility_model_diagnostics.csv
ELIGIBILITY_BIAS_REPORT.md
```

Criterio de alerta:

```text
|SMD| > 0.20
```

Si existe desequilibrio importante, no se cambia retrospectivamente la cohorte. Se limita la inferencia a la subpoblación elegible y se incluye una sensibilidad.

## 5.5 Perfil de entrenamiento recomendado

La arquitectura conserva V1:

```yaml
history_length: 12
input_dimension: 13
target_dimension: 9
hidden_dimension: 96
recurrent_layers: 1
dropout: 0.0
residual_mode: add_last
optimizer: AdamW
learning_rate: 0.001
weight_decay: 0.00001
gradient_clip_norm: 1.0
mse_weight: 1.0
device: cpu
torch_num_threads: 1
torch_num_interop_threads: 1
```

Perfil V2 recomendado:

```yaml
batch_size: 512
maximum_epochs: 60
early_stopping_patience: 10
early_stopping_minimum_delta: 0.0
```

Racional: con unas 7.900 filas de entrenamiento, `batch_size=512` y 60 épocas generan aproximadamente 900–1.000 actualizaciones máximas, cercanas al presupuesto de actualizaciones del entrenamiento histórico grande. Es una recomendación V2 predeclarada, no un resultado de V1.

También debe ejecutarse un diagnóstico development-only con el perfil legacy:

```yaml
batch_size: 2048
maximum_epochs: 20
early_stopping_patience: 5
```

La selección del perfil final debe realizarse sólo en `model_selection`, mediante una regla predefinida, antes de calibración y evaluación. No se permite elegir el perfil con el holdout.

## 5.6 Seeds

Conservar:

```text
1729
20260612
20260613
20260614
314159
```

Las seeds representan variabilidad algorítmica, no réplicas ecológicas.

### 5.6.1 Regla de disponibilidad familiar

```text
5/5 disponibles: completed
3–4/5 disponibles: partially_available
0–2/5 disponibles: model_family_unavailable
```

No reemplazar una seed fallida por otra.

Para declarar “P1 completado” en la tesis se exigen 5/5. Un cierre científico puede publicarse con menos, pero debe declarar la limitación.

## 5.7 Calibración

Usar únicamente `calibration_threshold`:

- seleccionar entre `identity`, `platt_logistic` e `isotonic_regression`;
- criterio primario: Brier;
- secundario: ECE;
- seleccionar threshold de alerta mediante F2;
- calcular cuantiles conformales para 0,80, 0,90 y 0,95;
- no recalibrar después de evaluación.

## 5.8 Endpoints

### Primario

```text
bloom_h a 30 µg/L
```

### Secundarios

```text
risk_chla continuo
estado trófico ordinal
estado S(t+h)
cobertura y ancho de intervalos
disponibilidad operacional
delta de planificación
```

### Sensibilidad

```text
25, 30, 33 y 50 µg/L
```

El cutoff de 30 es el único calibrado como endpoint primario. Los demás se reportan como sensibilidad predeclarada, sin seleccionar el valor más favorable.

## 5.9 Métricas

| Tipo | Métricas |
|---|---|
| Probabilidad | Brier, PR-AUC, ECE, reliability |
| Clasificación | F2, recall, precision, macro-F1 |
| Estado continuo | MAE, RMSE, NLL |
| Intervalos | PICP, MPIW, Winkler |
| Disponibilidad | success rate, evaluable rate, abstention/failure rate |
| Trófico | macro-F1, kappa cuadrática, MAE ordinal, error severo |
| Planificación | `delta_objective_vs_no_action`, soporte, costo, incertidumbre |

Siempre reportar:

```text
attempted
input_eligible
prediction_successful
target_available
metric_evaluable
shared_success
```

## 5.10 Inferencia primaria

### Predicción primaria

Usar el promedio de probabilidades de las cinco seeds como estimador de familia. No tratar las cinco seeds como cinco observaciones ecológicas.

### Bootstrap

Usar bootstrap agrupado por ubicación:

1. muestrear ubicaciones con reemplazo;
2. conservar todas sus filas origen–horizonte;
3. calcular diferencias pareadas en shared-success;
4. repetir 2.000 veces;
5. guardar todas las réplicas;
6. registrar réplicas no estimables.

Para PR-AUC, si una réplica tiene una sola clase:

- registrar `replicate_not_estimable`;
- no sustituir por cero;
- exigir al menos 95 % de réplicas válidas para emitir IC.

### Familias Holm recomendadas

```text
Familia A:
P1 vs B2, Brier, h1/h2/h3 = 3 contrastes primarios

Familia B:
P1 vs P0, Brier, h1/h2/h3 = 3 contrastes primarios

Familia C:
P1 vs B2 y P1 vs P0, PR-AUC, h1/h2/h3 = 6 contrastes secundarios

Familia D:
M0 vs P1 bajo degradación = universo completo predeclarado

Familia E:
acciones de planificación vs no_action = 9 contrastes
```

No reducir una familia por indisponibilidad.

## 5.11 Reglas de adjudicación

Para una métrica donde menor es mejor:

```text
superior: IC95 de delta(challenger - reference) completamente < 0
descriptively_favorable: estimación < 0, IC incluye 0
inconclusive: estimación e IC no permiten dirección estable
inferior: IC95 completamente > 0
not_estimable: sin shared-success o soporte estadístico
```

Para métricas donde mayor es mejor, invertir el signo.

No usar “equivalente” salvo diseño formal de equivalencia con márgenes predeclarados.

---

## 6. Estrategia de evaluación: dos capas

## 6.1 Capa L — `legacy_posthoc`

Reutiliza las 88 ubicaciones V1 y sus 4.488 orígenes.

Propósito:

- comprobar que P0/P1 pueden producir predicciones;
- completar comparaciones descriptivas;
- estudiar disponibilidad;
- ejecutar E6/E9 con P1;
- comparar con resultados V1.

Etiqueta obligatoria:

```text
posthoc_available
```

## 6.2 Capa F — `fresh_primary`

Se necesita para nuevas afirmaciones confirmatorias.

Orden de preferencia:

1. ubicaciones WQP nuevas no presentes en ninguna cohorte V1;
2. meses futuros incorporados después del protocol lock V2;
3. fuente externa compatible;
4. si ninguna existe, no hay capa confirmatoria.

### 6.2.1 Regla determinista de elección

Usando sólo información de inputs y procedencia:

```text
A. Elegir fresh-location si existen:
   >= 40 ubicaciones nuevas
   >= 500 intent origins por horizonte

B. En caso contrario, elegir forward-temporal si existen:
   >= 500 intent origins por horizonte
   target months posteriores al límite V1
   outcomes no abiertos antes del model lock V2

C. Si A y B fallan:
   fresh_primary = insufficient_support
   Closure V2 queda como análisis post hoc complementario
```

Los umbrales se verifican antes de abrir valores de outcome. No se reemplazan ubicaciones por ausencia posterior de target.

### 6.2.2 Qué significa “nueva ubicación”

La clave:

```text
source_id + site_id
```

debe estar ausente de las 441 ubicaciones V1, no sólo de las 88 holdout.

### 6.2.3 Claims permitidos

| Superficie | Claim máximo |
|---|---|
| Legacy V1 holdout | análisis retrospectivo complementario |
| Fresh WQP locations | evaluación interna en ubicaciones WQP no usadas |
| Forward temporal | evaluación temporal posterior al lock |
| Fuente externa | validación externa, sólo si target y contrato son comparables |

No usar “cuerpos de agua no vistos” sin un crosswalk auditado.

---

## 7. Estructura de archivos de V2

```text
docs/closure_v2/
  EXECUTION_GUIDE.md
  ANALYSIS_PLAN.md
  PROTOCOL_AMENDMENT_V2.md
  CLAIM_BOUNDARIES.md
  MANUSCRIPT_HANDOFF.md

configs/closure_v2/
  analysis_plan.yaml
  analysis_plan.schema.json
  eligibility_policy.yaml
  eligibility_policy.schema.json
  development_runtime.yaml
  development_runtime.schema.json
  model_benchmark.yaml
  calibration.yaml
  evaluation_cohorts.yaml
  degradation.yaml
  planning.yaml
  artifact_contract.yaml

src/experiments/closure_v2/
  __init__.py
  contracts.py
  hashing.py
  audit_v1_inputs.py
  build_eligibility.py
  audit_eligibility_bias.py
  build_shared_fit_keys.py
  train_temporal.py
  calibrate_temporal.py
  build_evaluation_inputs.py
  lock_models.py
  evaluate_models.py
  run_inference.py
  run_degradation.py
  run_planning.py
  synthesize.py
  certify.py

tests/closure_v2/
  test_contracts.py
  test_v1_input_audit.py
  test_eligibility.py
  test_shared_fit_keys.py
  test_temporal_training.py
  test_calibration.py
  test_evaluation_guard.py
  test_inference.py
  test_degradation.py
  test_planning.py
  test_synthesis.py
  test_certification.py

data/closure_v2/
  development/
  locked_evaluation/
  predictions_long.parquet.dvc
  degradation_masks.parquet.dvc

models/closure_v2/
  P0/
  P1/

reports/closure_v2/
  00_protocol/
  01_surface/
  02_models/
  03_calibration/
  04_evaluation/
  05_inference/
  06_degradation/
  07_planning/
  08_synthesis/
  09_certification/
```

Los directorios pesados contienen punteros DVC, no blobs Git.

---

## 8. Política Git y DVC

## 8.1 Rama

```bash
git switch main
git pull --ff-only
git switch -c closure-v2
```

Registrar:

```bash
git rev-parse HEAD
git rev-parse thesis-closure-v1^{}
git merge-base --is-ancestor thesis-closure-v1 HEAD
git status --short --untracked-files=all
```

## 8.2 Tags recomendados

```text
closure-v2-protocol
closure-v2-development
closure-v2-model-lock
closure-v2-results
thesis-closure-v2
```

Todos anotados e inmutables.

## 8.3 Commits

Codex no debe ejecutar `git commit` ni `git push`. El usuario revisa y publica cada gate.

Mensajes sugeridos:

```text
Open Closure V2 protocol
Materialize Closure V2 eligibility surface
Fit Closure V2 P0 and P1 temporal families
Publish Closure V2 model lock
Publish Closure V2 evaluation results
Publish Closure V2 degradation and planning evidence
Publish Closure V2 synthesis
Publish Closure V2 final certification
```

## 8.4 DVC

Usar:

```bash
scripts/dvc_data_assistant.sh doctor
scripts/prepare_commit_artifacts.sh
scripts/list_publication_candidates.sh
scripts/check_repo_publication_ready.sh
```

Reglas:

- credenciales sólo en rutas ignoradas;
- bucket real nunca en Git;
- modelos `.pt`, Parquets y distribuciones bootstrap bajo DVC;
- manifests, hashes, CSV pequeños y Markdown bajo Git;
- `dvc push` dirigido antes de publicar el pointer;
- restauración en clone/caché vacío para certificación final.

---

## 9. Protocolo de trabajo con GPT‑Codex — inteligencia media

## 9.1 Por qué los prompts deben ser atómicos

Con inteligencia media, Codex funciona mejor cuando:

- recibe una sola fase;
- conoce archivos exactos;
- conoce prohibiciones;
- recibe tests y criterios de aceptación;
- no debe inferir el diseño científico;
- no debe reorganizar el repositorio completo;
- entrega un reporte estructurado.

No pedir:

```text
“Implementa Closure V2 completo.”
```

Sí pedir:

```text
“Implementa únicamente el ledger de elegibilidad descrito en la fase 2,
en los paths enumerados, con estos tests y sin entrenar modelos.”
```

## 9.2 Prompt base obligatorio

Anteponer a cada prompt:

```text
Trabajas en el repositorio ejherran/lentic-pipe, rama closure-v2.

Autoridades:
- thesis-closure-v1 es inmutable.
- Closure V1 science commit:
  ea8ddce7f8edb9a61db97e29178e52603fa371b1.
- Closure V1 certification commit:
  eb07598aa54a0944d1a87fe46d62415d0a4454aa.

Reglas:
1. Trabaja exclusivamente la fase indicada.
2. No modifiques configs/docs/reports/data de closure_v1.
3. Implementa de forma aditiva bajo closure_v2.
4. No leas outcomes de evaluación salvo autorización explícita de la fase.
5. No hagas commit, push, tag ni dvc push.
6. No crees versiones duplicadas de archivos.
7. No hagas refactors amplios.
8. Antes de editar, inspecciona los archivos de autoridad citados.
9. Si detectas una contradicción, detente y crea un reporte STOP; no improvises.
10. Ejecuta los tests específicos y luego la suite pertinente.
11. Al terminar, informa:
   - resumen;
   - archivos modificados;
   - comandos ejecutados;
   - tests;
   - artefactos generados;
   - limitaciones;
   - estado Git/DVC;
   - siguiente gate recomendado.
```

## 9.3 Prompt de reentrada para una sesión nueva

```text
Lee, en este orden:
1. docs/closure_v2/EXECUTION_GUIDE.md
2. docs/closure_v2/ANALYSIS_PLAN.md
3. reports/closure_v2/00_protocol/implementation_state.json
4. reports/closure_v2/00_protocol/EXECUTION_LOG.md
5. el manifest más reciente de la fase actual.

Ejecuta sólo comprobaciones read-only:
- git status --short --untracked-files=all
- git log -1 --oneline
- git rev-parse HEAD
- git rev-parse thesis-closure-v1^{}
- verifica que el tag V1 no cambió.

Resume el estado y detente. No edites todavía.
```

## 9.4 Contrato de salida de Codex

Codex debe terminar cada fase con:

```markdown
## Resultado
PASS | PARTIAL | STOP

## Cambios
- archivo
- propósito

## Evidencia
- path
- hash/conteo relevante

## Pruebas
- comando
- resultado

## Riesgos o límites
- ...

## Acciones manuales del usuario
- revisar
- ejecutar DVC si procede
- commit sugerido
```

---

# 10. Fase 0 — Reentrada, baseline e inmutabilidad

## 10.1 Objetivo

Crear la rama y registrar el estado inicial sin tocar ciencia.

## 10.2 Acciones

1. Verificar tag y commits V1.
2. Verificar `main`.
3. Crear `closure-v2`.
4. Generar un receipt de entrada.
5. Generar inventario de paths V1.
6. Copiar esta guía a `docs/closure_v2/EXECUTION_GUIDE.md`.
7. Crear `implementation_state.json` y `EXECUTION_LOG.md`.

## 10.3 Artefactos

```text
reports/closure_v2/00_protocol/entry_receipt.json
reports/closure_v2/00_protocol/v1_reference_manifest.json
reports/closure_v2/00_protocol/implementation_state.json
reports/closure_v2/00_protocol/EXECUTION_LOG.md
```

`v1_reference_manifest.json` debe registrar:

- tag object;
- peeled commit;
- science commit;
- lista de namespaces V1;
- digest ordenado de paths/hashes;
- fecha de captura;
- base commit V2.

## 10.4 Prompt para Codex

```text
FASE 0: reentrada e inmutabilidad.

Inspecciona README.md, el tag thesis-closure-v1 y los manifiestos terminales V1.
Crea únicamente el scaffold de docs/configs/reports/src/tests para closure_v2
y los cuatro receipts indicados en la guía.

Implementa un auditor read-only:
src/experiments/closure_v2/audit_v1_inputs.py

Debe:
- resolver thesis-closure-v1^{};
- verificar los commits V1 esperados;
- generar un inventario determinista;
- fallar si se intenta escribir en namespaces closure_v1;
- no abrir Parquets;
- no ejecutar DVC;
- no modificar V1.

Agrega tests sintéticos del auditor.
No implementes protocolo, elegibilidad ni entrenamiento.
```

## 10.5 Pruebas

```bash
poetry run pytest tests/closure_v2/test_v1_input_audit.py -q
poetry run ty check
git diff --name-only thesis-closure-v1...HEAD
```

## 10.6 Criterio de aceptación

- tag V1 coincide;
- no hay cambios V1;
- receipts deterministas;
- tests pasan;
- ningún outcome abierto.

---

# 11. Fase 1 — Protocolo V2 y prerregistro

## 11.1 Objetivo

Publicar el diseño antes de entrenar P0/P1.

## 11.2 Archivos

```text
docs/closure_v2/ANALYSIS_PLAN.md
docs/closure_v2/PROTOCOL_AMENDMENT_V2.md
docs/closure_v2/CLAIM_BOUNDARIES.md
configs/closure_v2/analysis_plan.yaml
configs/closure_v2/analysis_plan.schema.json
configs/closure_v2/eligibility_policy.yaml
configs/closure_v2/eligibility_policy.schema.json
configs/closure_v2/model_benchmark.yaml
configs/closure_v2/evaluation_cohorts.yaml
reports/closure_v2/00_protocol/protocol_lock.json
reports/closure_v2/00_protocol/artifact_inventory.csv
```

## 11.3 Contenido mínimo

- objetivo V2;
- diferencia frente a V1;
- complete-case primary;
- shared-fit P0/P1;
- umbrales mínimos;
- seeds;
- arquitectura;
- roles;
- endpoints;
- métricas;
- familias Holm;
- dos capas de evaluación;
- reglas de no sustitución;
- reglas de claims;
- plan de DVC;
- STOP conditions.

## 11.4 Prompt para Codex

```text
FASE 1: protocolo y prerregistro Closure V2.

A partir de esta guía y de los contratos V1, crea el plan humano, YAML,
schemas y claim boundaries de Closure V2.

No copies ciegamente los schemas V1. Reutiliza conceptos, pero simplifica la
topología: protocol lock, development lock, model lock, evaluation activation,
results, synthesis y certification.

Fija exactamente:
- política complete-case;
- umbrales de elegibilidad;
- shared-fit P0/P1;
- cinco seeds;
- arquitectura temporal;
- perfil V2 y perfil legacy diagnóstico;
- capas legacy_posthoc y fresh_primary;
- familias Holm A-E;
- prohibición de tuning con evaluación;
- criterio para distinguir post hoc y confirmatorio.

Implementa validación de schema y generación manifest-last del protocol lock.
No leas Parquet ni outcomes.
```

## 11.5 Pruebas

```bash
poetry run pytest tests/closure_v2/test_contracts.py -q
poetry run python -m src.experiments.closure_v2.contracts \
  --validate configs/closure_v2/analysis_plan.yaml
poetry run ty check
```

## 11.6 Revisión humana obligatoria

Antes de commit/tag:

- leer todo el plan;
- confirmar umbrales;
- confirmar cohort hierarchy;
- confirmar métricas;
- confirmar familias Holm;
- confirmar que no promete superioridad.

Tag sugerido:

```text
closure-v2-protocol
```

---

# 12. Fase 2 — Restauración de inputs y ledger de elegibilidad

## 12.1 Objetivo

Demostrar, con evidencia, qué filas pueden entrenar P0/P1.

## 12.2 Inputs preferentes

Reutilizar, sin modificar:

```text
reports/closure_v1/01_surface/sequences/P0/
reports/closure_v1/01_surface/sequences/P1/
data/closure_v1/development/sequences/
reports/closure_v1/01_surface/anfis/
data/closure_v1/development/anfis/
reports/closure_v1/01_surface/expert/
data/closure_v1/development/expert/
```

Cada input se liga por:

- path;
- source commit;
- bytes;
- SHA-256;
- DVC md5/size cuando aplique.

## 12.3 Outputs

```text
data/closure_v2/development/fit_eligibility.parquet.dvc
data/closure_v2/development/shared_fit_keys.parquet.dvc
reports/closure_v2/01_surface/eligibility_counts.csv
reports/closure_v2/01_surface/eligibility_by_role.csv
reports/closure_v2/01_surface/eligibility_by_location.csv
reports/closure_v2/01_surface/eligibility_covariate_balance.csv
reports/closure_v2/01_surface/ELIGIBILITY_BIAS_REPORT.md
reports/closure_v2/01_surface/eligibility_manifest.json
```

## 12.4 Esquema mínimo del ledger

```text
source_id
site_id
origin_year_month
target_year_month
time_role
model_id
base_seed
intent_to_fit
sequence_status
failure_reason
input_complete
target_complete
fit_eligible
shared_fit_eligible
exclusion_reason
```

## 12.5 Prompt para Codex

```text
FASE 2: ledger de elegibilidad.

Implementa:
- build_eligibility.py
- build_shared_fit_keys.py
- audit_eligibility_bias.py

Lee únicamente artefactos development-only declarados en el protocol lock.
No abras evaluación V1 ni outcomes post-2021.

La política primaria no exige que todas las filas sean success. Autoriza el
fit cuando se cumplen los umbrales agregados. Conserva todas las filas en el
ledger.

P0 y P1 deben producir:
- conteos exactos por rol y seed;
- intersección exacta de shared-fit keys;
- digests de claves;
- balance elegible/no elegible;
- reporte de sesgo.

Falla si:
- aparece holdout;
- aparece post-2021;
- aparece Chl-a observada o lineage prohibido;
- P0 y P1 no pueden emparejarse;
- un input no coincide con su hash V1.

No entrenes modelos.
```

## 12.6 Tests esenciales

- una fila incompleta no invalida toda la familia;
- la fila incompleta permanece en ledger;
- umbral < 0,90 falla cerrado;
- 8.925/9.413 autoriza fit;
- no hay overlap holdout;
- shared keys idénticas por seed;
- no hay silencios;
- manifests deterministas.

## 12.7 Comandos

```bash
poetry run pytest tests/closure_v2/test_eligibility.py \
  tests/closure_v2/test_shared_fit_keys.py -q

poetry run python -m src.experiments.closure_v2.build_eligibility \
  --config configs/closure_v2/eligibility_policy.yaml

poetry run python -m src.experiments.closure_v2.audit_eligibility_bias \
  --config configs/closure_v2/analysis_plan.yaml
```

## 12.8 Gate

No continuar si:

- fracción real < 0,90;
- train < 5.000;
- selection < 500;
- calibration < 200;
- el sesgo no puede caracterizarse;
- hay fuga.

Tag sugerido:

```text
closure-v2-development
```

---

# 13. Fase 3 — Dataset temporal y entrenamiento P0/P1

## 13.1 Objetivo

Emitir modelos reales para los cinco slots.

## 13.2 Implementación

Crear un entrenador V2 nuevo. No editar el trainer V1 para cambiar su semántica histórica.

`train_temporal.py` debe:

1. validar protocol lock;
2. validar development lock;
3. cargar shared-fit keys;
4. filtrar sólo `fit_eligible`;
5. conservar el ledger completo fuera de la pérdida;
6. fijar seeds antes de construir el modelo;
7. entrenar P0 y P1;
8. evaluar en `model_selection`;
9. restaurar best checkpoint;
10. recalcular blend una sola vez;
11. emitir manifest-last;
12. registrar fallos sin reemplazo.

## 13.3 Artefactos por modelo/seed

```text
models/closure_v2/P1/seed_1729/model.pt.dvc
models/closure_v2/P1/seed_1729/checkpoint.pt.dvc
reports/closure_v2/02_models/P1/seed_1729/training_curve.csv
reports/closure_v2/02_models/P1/seed_1729/selection_metrics.csv
reports/closure_v2/02_models/P1/seed_1729/blend_weights.csv
reports/closure_v2/02_models/P1/seed_1729/report.md
reports/closure_v2/02_models/P1/seed_1729/manifest.json
```

Repetir para P0 y las cinco seeds.

## 13.4 Prompt para Codex — implementación

```text
FASE 3A: implementar el trainer V2.

Crea src/experiments/closure_v2/train_temporal.py y sus tests.

Reutiliza kernels matemáticos probados del trainer histórico cuando sea seguro,
pero no modifiques el comportamiento V1.

Cambio central:
- elegibilidad agregada y complete-case;
- no all-or-nothing;
- shared-fit P0/P1;
- ledger preservado.

Implementa perfiles:
- v2_primary: batch 512, max 60, patience 10;
- legacy_diagnostic: batch 2048, max 20, patience 5.

El perfil final se decide con model_selection-only según la regla del config.
La evaluación permanece prohibida.

Cubre con tests:
- dataset sintético con una fila incompleta entrena;
- umbral insuficiente bloquea;
- P0/P1 usan claves idénticas;
- seed determinista;
- no resume;
- best checkpoint;
- manifest-last;
- no replacement.
No ejecutes entrenamientos reales todavía.
```

## 13.5 Prompt para Codex — ejecución

```text
FASE 3B: ejecutar entrenamientos reales P0/P1.

Verifica primero:
- Git limpio;
- development lock válido;
- DVC inputs presentes;
- no outcomes de evaluación accesibles;
- cinco seeds registradas.

Ejecuta primero un smoke limitado con datos sintéticos.
Después ejecuta los diez slots reales.

No selecciones la mejor seed.
No reintentes cambiando hiperparámetros.
Si un slot falla, conserva el fallo y detente antes de cualquier ajuste ad hoc.

Genera un resumen familiar P0/P1 con:
- slots disponibles;
- filas intent/eligible;
- best epoch;
- métricas selection;
- hashes de modelo/checkpoint;
- tiempo de ejecución;
- entorno.
```

## 13.6 Criterios de aceptación

Para “P1 completado”:

```text
5/5 model.pt
5/5 checkpoint.pt
5/5 manifest status=completed
5/5 selection metrics
0 holdout rows
0 post-2021 rows
0 current-Chl-a lineage
```

Si 3–4 slots pasan, continuar sólo como `partially_available`.

---

# 14. Fase 4 — Calibración y model lock

## 14.1 Objetivo

Congelar modelos, calibradores y thresholds antes de evaluar.

## 14.2 Outputs

```text
reports/closure_v2/03_calibration/calibrator_specs.json
reports/closure_v2/03_calibration/calibration_metrics.csv
reports/closure_v2/03_calibration/alert_thresholds.csv
reports/closure_v2/03_calibration/conformal_quantiles.csv
reports/closure_v2/03_calibration/model_availability.csv
reports/closure_v2/03_calibration/calibration_manifest.json
reports/closure_v2/00_protocol/model_lock.json
reports/closure_v2/00_protocol/model_lock_manifest.json
```

## 14.3 Prompt para Codex

```text
FASE 4: calibración y model lock.

Implementa calibración exclusivamente sobre 2021.
No abras ninguna evaluación.

Para cada modelo/seed/horizonte:
- fit de calibrador según regla predeclarada;
- threshold F2;
- q conformal 0.80/0.90/0.95;
- diagnósticos Brier/ECE;
- manifest y hashes.

Genera model_lock con:
- modelos;
- checkpoints;
- profile;
- seeds;
- shared-fit digest;
- calibradores;
- thresholds;
- q;
- cohorts;
- hipótesis;
- output contract;
- comandos sellados de evaluación.

El model lock se escribe al final.
Falla si cualquier artefacto no coincide con su hash o si aparece una ruta de
evaluación abierta.
```

## 14.4 Validación

```bash
poetry run pytest tests/closure_v2/test_calibration.py \
  tests/closure_v2/test_evaluation_guard.py -q
poetry run ty check
```

Tag sugerido:

```text
closure-v2-model-lock
```

---

# 15. Fase 5 — Construcción de evaluación fresca y activación

## 15.1 Objetivo

Definir la superficie sin usar valores futuros para seleccionar casos.

## 15.2 Auditoría de candidatos

Crear:

```text
reports/closure_v2/00_protocol/fresh_candidate_inventory.csv
reports/closure_v2/00_protocol/fresh_cohort_decision.json
reports/closure_v2/00_protocol/fresh_cohort_manifest.json
```

El decision record debe declarar:

```text
fresh_location
forward_temporal
external
insufficient_support
```

## 15.3 Input-only bundle

```text
data/closure_v2/locked_evaluation/input_history.parquet.dvc
data/closure_v2/locked_evaluation/intent_origins.parquet.dvc
data/closure_v2/locked_evaluation/origin_features.parquet.dvc
data/closure_v2/locked_evaluation/sequence_features.parquet.dvc
reports/closure_v2/01_surface/locked_evaluation_input_manifest.json
```

No incluir values de target.

## 15.4 Activación

Crear un `outcome_access_log.jsonl` exclusivo de V2.

La activación debe:

- existir después del model lock;
- registrar el commit y contract hash;
- autorizar una ejecución;
- ser append-only;
- fallar si el model lock cambia.

## 15.5 Prompt para Codex

```text
FASE 5: cohorte fresca y activación.

Primero construye el inventario input-only y aplica la jerarquía del protocolo.
No inspecciones outcome values.

Si no existe soporte fresco suficiente:
- registra fresh_primary=insufficient_support;
- conserva legacy_posthoc;
- no inventes una cohorte.

Si existe:
- congela assignment;
- crea input-only bundle;
- audita overlap con todas las ubicaciones V1 cuando sea fresh-location;
- audita fechas cuando sea forward-temporal;
- publica manifest.

Después implementa la activación one-shot V2.
No ejecutes el benchmark en este prompt.
```

## 15.6 STOP

Detener si:

- el outcome fue leído antes del lock;
- se seleccionaron ubicaciones por desempeño futuro;
- se reemplazaron ubicaciones sin targets;
- hay overlap no declarado;
- el log no es append-only.

---

# 16. Fase 6 — Evaluación P0/P1 y benchmark

## 16.1 Objetivo

Generar predicciones y métricas con los modelos congelados.

## 16.2 Comparadores

Primarios:

```text
P1 vs B2
P1 vs P0
```

Secundarios:

```text
P1 vs B1
P1 vs A1
A1 vs A0
M0 vs P1
```

No es obligatorio declarar un ganador global.

## 16.3 Outputs

```text
data/closure_v2/predictions_long.parquet.dvc
reports/closure_v2/04_evaluation/model_metrics_long.csv
reports/closure_v2/04_evaluation/model_availability.csv
reports/closure_v2/04_evaluation/intent_to_predict_funnel.csv
reports/closure_v2/04_evaluation/pairwise_common_rows.csv
reports/closure_v2/04_evaluation/threshold_sensitivity.csv
reports/closure_v2/04_evaluation/uncertainty_ledger.csv
reports/closure_v2/04_evaluation/BENCHMARK_REPORT.md
reports/closure_v2/04_evaluation/evaluation_manifest.json
```

Separar:

```text
evaluation_cohort=legacy_posthoc
evaluation_cohort=fresh_primary
estimand=observation_weighted
estimand=site_weighted
```

## 16.4 Prompt para Codex

```text
FASE 6: evaluación sellada.

Verifica model lock y activation.
Ejecuta modelos sin refit, recalibración ni cambio de threshold.

Preserva todos los intent origins.
Para cada modelo/seed/horizonte registra:
- prediction_status;
- failure_reason;
- target availability;
- metric evaluability;
- shared-success.

Genera métricas observation-weighted y site-weighted por separado.
Genera ensemble de cinco seeds y diagnósticos por seed.
Evalúa 30 como endpoint primario y 25/33/50 como sensibilidad.
No hagas inferencia estadística todavía.
No mezcles legacy_posthoc con fresh_primary.
```

## 16.5 Validación

- número de intentos igual al manifest;
- ninguna fila omitida;
- no hay ceros falsos;
- P0/P1 disponibles donde corresponde;
- hashes;
- reproducibilidad de una segunda ejecución sobre outputs temporales;
- no refit.

---

# 17. Fase 7 — Inferencia estadística

## 17.1 Objetivo

Convertir deltas descriptivos en evidencia con IC y multiplicidad.

## 17.2 Outputs

```text
reports/closure_v2/05_inference/site_level_losses.csv
reports/closure_v2/05_inference/pairwise_effects.csv
reports/closure_v2/05_inference/multiplicity_report.csv
reports/closure_v2/05_inference/bootstrap_summary.csv
reports/closure_v2/05_inference/bootstrap_distributions.parquet.dvc
reports/closure_v2/05_inference/STATISTICAL_INFERENCE_REPORT.md
```

## 17.3 Prompt para Codex

```text
FASE 7: inferencia agrupada.

Implementa bootstrap pareado por ubicación con 2.000 réplicas.
Usa ensemble de seeds como predicción primaria.
No poolem seeds como observaciones independientes.

Calcula:
- P1 vs B2 Brier h1-h3;
- P1 vs P0 Brier h1-h3;
- PR-AUC secundario;
- proporción de ubicaciones con mejora;
- IC95;
- p bootstrap si está predeclarado;
- Holm sin reducir familias.

Registra réplicas PR-AUC no estimables y exige >=95 % válidas.
Mantén legacy_posthoc y fresh_primary separados.
Si fresh_primary no existe, ningún resultado se etiqueta confirmatory.
```

## 17.4 Criterio de aceptación

- claves comunes exactas;
- unidad estadística ubicación;
- seeds no pseudo-replicadas;
- familias completas;
- distribuciones guardadas;
- estados no estimables explícitos.

---

# 18. Fase 8 — Degradación M0–P1

## 18.1 Objetivo

Completar la comparación que V1 no pudo estimar.

## 18.2 Diseño

### Legacy

Reutilizar masks V1 cuando sean compatibles, ligándolas por hash.

### Fresh

Generar masks deterministas V2:

- MCAR;
- bloques temporales;
- eliminación de nutrientes;
- eliminación de claridad;
- eliminación de oxígeno;
- combinaciones severas.

Aplicar las mismas masks a M0 y P1.

### Política primaria

Evaluación de degradación en inferencia con modelos congelados. No refit por escenario.

## 18.3 Métricas

- PR-AUC;
- Brier;
- F2;
- PICP;
- MPIW;
- Winkler;
- availability;
- failure rate;
- AUPD;
- crossover sólo si está respaldado.

## 18.4 Outputs

```text
data/closure_v2/degradation_masks.parquet.dvc
reports/closure_v2/06_degradation/degradation_metrics.csv
reports/closure_v2/06_degradation/pairwise_effects.csv
reports/closure_v2/06_degradation/failure_registry.csv
reports/closure_v2/06_degradation/aupd.csv
reports/closure_v2/06_degradation/DEGRADATION_REPORT.md
```

## 18.5 Prompt para Codex

```text
FASE 8: degradación emparejada M0-P1.

Usa modelos y calibradores congelados.
Aplica masks idénticas sobre claves comunes.
No reentrenes por escenario.

Preserva:
- intent origins;
- model availability;
- shared-success;
- fallos;
- horizonte;
- seed;
- cohort.

Calcula métricas y deltas agrupados.
No declares crossover por una sola métrica o un solo nivel.
No interpretes intervalos tipo 2 y probabilísticos como idénticos.
```

---

# 19. Fase 9 — Planificación con P1

## 19.1 Objetivo

Hacer estimables las nueve acciones sin afirmar causalidad.

## 19.2 Acciones

Conservar, salvo modificación preprotocolizada:

```text
tp_reduction_10
tp_reduction_25
tn_reduction_10
tp_tn_reduction_10
clarity_mild
clarity_strong
oxygen_support_05
nutrient_clarity_mild
nutrient_clarity_strong
```

## 19.3 Endpoint

```text
delta_objective_vs_no_action
```

Registrar también:

- delta risk;
- cost;
- support violation;
- uncertainty change;
- availability.

## 19.4 Outputs

```text
reports/closure_v2/07_planning/planning_bootstrap.csv
reports/closure_v2/07_planning/planning_sensitivity.csv
reports/closure_v2/07_planning/ecological_coherence.csv
reports/closure_v2/07_planning/PLANNING_REPORT.md
reports/closure_v2/07_planning/planning_origin_deltas.parquet.dvc
```

## 19.5 Prompt para Codex

```text
FASE 9: planificación contrafactual.

Usa rollouts P1 congelados.
Compara cada acción con no_action sobre las mismas claves.
Calcula delta_objective_vs_no_action, IC95 por ubicación y Holm E=9.
Conserva costo, soporte e incertidumbre.

Prohibiciones:
- causalidad de campo;
- recomendación oficial;
- optimalidad universal;
- reemplazar acciones no estimables;
- seleccionar sólo acciones favorables.

Si ninguna acción supera no_action, publícalo como resultado válido.
```

---

# 20. Fase 10 — Síntesis y paquete para tesis

## 20.1 Objetivo

Transformar resultados en evidencia lista para actualizar LaTeX.

## 20.2 Outputs obligatorios

```text
reports/closure_v2/08_synthesis/FINAL_CLOSURE_MATRIX.csv
reports/closure_v2/08_synthesis/THESIS_CLAIM_EVIDENCE_MATRIX.csv
reports/closure_v2/08_synthesis/FINAL_CLOSURE_REPORT.md
reports/closure_v2/08_synthesis/MANUSCRIPT_CHANGE_MAP.md
reports/closure_v2/08_synthesis/THESIS_TABLES/
reports/closure_v2/08_synthesis/THESIS_FIGURES/
reports/closure_v2/08_synthesis/synthesis_manifest.json
```

## 20.3 Tablas recomendadas

```text
T01 V2 model availability
T02 Fit eligibility and attrition
T03 Eligibility bias
T04 Benchmark observation-weighted
T05 Benchmark site-weighted
T06 P1 vs B2 inferential effects
T07 P1 vs P0 inferential effects
T08 Threshold sensitivity
T09 Uncertainty
T10 Degradation M0-P1
T11 Planning
T12 V1-V2 evidence boundary
T13 Software evidence
T14 Hypothesis adjudication
```

## 20.4 Figuras recomendadas

```text
F01 Fit eligibility funnel
F02 Eligibility by location/time
F03 Training curves P0/P1
F04 Benchmark metrics and availability
F05 Paired effects with IC
F06 Calibration and uncertainty
F07 Degradation curves
F08 Planning effects
F09 V1-V2 provenance
F10 Hypothesis verdicts
```

## 20.5 Claim matrix

Cada claim debe incluir:

```text
claim_id
chapter
section
claim_text
claim_status
cohort
estimand
artifact_path
row_filter
metric
value
denominator
authority_commit
limitation
allowed_wording
forbidden_wording
```

## 20.6 Prompt para Codex

```text
FASE 10: síntesis para tesis.

Consume sólo inputs estructurados allowlisted.
No leas raw targets ni private/FULL.md.
No recalcules modelos ni métricas.

Genera matrices, reporte, tablas y figuras deterministas.
Distingue:
- V1 frozen evidence;
- V2 legacy_posthoc;
- V2 fresh_primary;
- software evidence.

Toda cifra debe tener cohort, estimand, denominator y artifact path.
No modifiques todavía el proyecto LaTeX.
El synthesis_manifest se escribe al final.
```

## 20.7 Gate editorial

Antes de tocar la tesis:

- aprobar `FINAL_CLOSURE_REPORT.md`;
- aprobar claim matrix;
- comprobar que los resultados no fueron seleccionados por conveniencia;
- comprobar captions;
- comprobar límites.

---

# 21. Fase 11 — Certificación final del repositorio

## 21.1 Objetivo

Certificar ejecución, restaurabilidad y contrato de software. No “certificar eficacia”.

## 21.2 Controles

```bash
poetry install --with dev,api,modeling,sources,data-versioning
poetry run pytest
poetry run ty check
poetry check --lock
scripts/check_repo_publication_ready.sh
```

Además:

- OpenAPI válido;
- workflows sintéticos P0/P1;
- smoke de calibración;
- smoke de evaluación sin outcomes reales;
- restauración DVC dirigida en clone/caché vacío;
- hashes;
- no credenciales;
- no URLs privadas;
- no paths absolutos;
- no timestamps innecesarios en artefactos deterministas.

## 21.3 Outputs

```text
reports/closure_v2/09_certification/public_tests.xml
reports/closure_v2/09_certification/test_report.md
reports/closure_v2/09_certification/openapi.json
reports/closure_v2/09_certification/openapi_contract_report.md
reports/closure_v2/09_certification/end_to_end_report.md
reports/closure_v2/09_certification/environment.json
reports/closure_v2/09_certification/FINAL_CERTIFICATION_REPORT.md
reports/closure_v2/09_certification/final_certification_manifest.json
```

## 21.4 Prompt para Codex

```text
FASE 11: certificación final.

Construye una certificación outcome-free sobre el commit candidato final.

Debe verificar:
- suite pública;
- tests V2;
- ty;
- Poetry lock;
- OpenAPI;
- E2E sintético;
- restauración exacta de todos los pointers V2 requeridos en clone/cache vacío;
- redacción de secretos;
- igualdad de paths fuera del bundle de certificación.

No reejecutes ciencia.
No abras Parquets restaurados en Python salvo que el contrato de certificación
lo autorice explícitamente; preferir autenticación por DVC hash/size.
Manifest-last.
```

Tag terminal:

```text
thesis-closure-v2
```

---

# 22. Fase 12 — Handoff al proyecto LaTeX

## 22.1 Objetivo

Proporcionar al agente que actualice la tesis un paquete inequívoco.

## 22.2 `MANUSCRIPT_CHANGE_MAP.md`

Debe indicar, por sección:

```text
Resumen
Abstract
Capítulo III
Capítulo IV
Capítulo V
Anexos
```

Para cada cambio:

- claim nuevo;
- claim retirado;
- tabla;
- figura;
- artefacto;
- denominador;
- wording permitido;
- wording prohibido.

## 22.3 Posibles escenarios

### A. P1 favorable en fresh-primary

Se puede elevar H2 a apoyo confirmatorio condicionado a esa cohorte.

### B. P1 favorable sólo en legacy-posthoc

Se puede afirmar evidencia retrospectiva complementaria, no confirmación independiente.

### C. P1 similar o mixto

La tesis mejora porque H2 se vuelve estimable, aunque no exista superioridad.

### D. P1 inferior

Resultado negativo fuerte: la complejidad temporal adaptativa no aporta en esa superficie.

### E. P1 vuelve a ser no disponible

La limitación es estructural y debe mantenerse.

---

# 23. Matriz completa de evidencia requerida

| Bloque | Evidencia mínima |
|---|---|
| Protocolo | plan humano, YAML, schema, lock, inventory |
| Inmutabilidad V1 | reference manifest, tag/commit receipt |
| Elegibilidad | ledger completo, shared keys, bias report |
| P0 | 5 modelos/checkpoints, métricas, manifests |
| P1 | 5 modelos/checkpoints, métricas, manifests |
| Calibración | calibradores, thresholds, q, diagnostics |
| Cohorte | assignment, input-only manifest, access log |
| Benchmark | predictions, metrics, availability, paired rows |
| Inferencia | site losses, effects, bootstrap, Holm |
| Incertidumbre | coverage, width, Winkler, reliability |
| Degradación | masks, metrics, failures, AUPD |
| Planificación | origin deltas, effects, support, cost |
| Síntesis | closure matrix, claims, tables, figures |
| Software | tests, OpenAPI, E2E, environment |
| DVC | pointers y restore receipts |
| Tesis | manuscript change map |

---

# 24. Reglas de STOP

Detener inmediatamente si:

1. cambia `thesis-closure-v1`;
2. aparece un diff no autorizado en V1;
3. se leen outcomes frescos antes del model lock;
4. se elige una cohorte por outcome values;
5. se cambia un threshold después de evaluación;
6. se modifica la arquitectura por resultado del holdout;
7. se elimina una fila fallida sin ledger;
8. P0 y P1 usan distintas claves primarias;
9. se sustituye una seed;
10. se reduce Holm por indisponibilidad;
11. se mezclan legacy y fresh;
12. se mezclan observation/site weighted;
13. se llama externo a WQP interno;
14. se formula causalidad;
15. un artefacto no tiene hash;
16. un pointer DVC no está publicado;
17. una cifra no tiene denominador;
18. una figura no se reproduce desde datos estructurados;
19. Codex propone un refactor masivo no necesario;
20. el repositorio contiene credenciales.

Crear:

```text
reports/closure_v2/STOP_REPORT_<gate>.md
```

No intentar “arreglar rápido” después de abrir outcomes.

---

# 25. Solución de problemas

## 25.1 P1 tiene NaN en pérdida

Verificar:

- filtro `fit_eligible`;
- finitud de nueve targets;
- log variance clip;
- grad clip;
- batch;
- dtype;
- orden de canales.

No imputar targets para completar el fit primario.

## 25.2 Algunas ubicaciones concentran fallos

Reportar concentración. Ejecutar sensibilidad excluyendo sitios extremos sólo como análisis secundario predeclarado.

## 25.3 Falta soporte fresh-primary

Cerrar V2 como post hoc. No fabricar validación independiente.

## 25.4 P1 mejora PR-AUC pero empeora Brier

Interpretar como mayor discriminación y peor calibración. No declarar superioridad global.

## 25.5 P1 mejora Brier pero tiene menor availability

Presentar calidad condicional y disponibilidad juntas.

## 25.6 M0 tiene mejor cobertura e intervalos muy anchos

Interpretar como comportamiento precautorio, no superioridad automática.

## 25.7 Planificación arroja efectos positivos fuera de soporte

No autorizar recomendación. El soporte tiene precedencia.

## 25.8 Codex genera demasiados archivos

Detener. Consolidar roles dentro de los namespaces canónicos. Git conserva versiones; no usar sufijos de versión.

---

# 26. Definition of Done

## 26.1 Cierre científico de V2

```text
[ ] V1 inmutable
[ ] protocolo V2 publicado antes de evaluación
[ ] ledger completo
[ ] sesgo de elegibilidad auditado
[ ] shared-fit P0/P1
[ ] P0 5/5
[ ] P1 5/5
[ ] calibradores y thresholds bloqueados
[ ] legacy_posthoc evaluado
[ ] fresh_primary evaluado o insufficient_support explícito
[ ] benchmark y availability
[ ] bootstrap por ubicación
[ ] Holm completo
[ ] incertidumbre
[ ] degradación M0-P1
[ ] planificación P1
[ ] claim matrix
[ ] final report
```

## 26.2 Cierre de software

```text
[ ] pytest PASS
[ ] ty PASS
[ ] poetry check --lock PASS
[ ] OpenAPI PASS
[ ] E2E PASS
[ ] DVC restore PASS
[ ] publication readiness PASS
[ ] no secretos
[ ] manifest-last
[ ] tag thesis-closure-v2 publicado
```

## 26.3 Cierre para actualización de tesis

```text
[ ] MANUSCRIPT_CHANGE_MAP.md
[ ] tablas finales
[ ] figuras finales
[ ] wording permitido/prohibido
[ ] resumen/abstract boundaries
[ ] adjudicación H1-H5
[ ] limitaciones
[ ] freeze/commit/tag exactos
```

---

# 27. Secuencia de prompts recomendada para Codex

Ejecutar exactamente en este orden:

```text
P00 Reentrada read-only
P01 Scaffold e inmutabilidad
P02 Protocolo y schemas
P03 Protocol lock
P04 Restore/audit inputs
P05 Ledger de elegibilidad
P06 Sesgo de elegibilidad
P07 Trainer unitario
P08 Entrenamiento P0/P1
P09 Calibración
P10 Model lock
P11 Cohorte fresca/input-only
P12 Activation
P13 Benchmark
P14 Inferencia
P15 Degradación
P16 Planificación
P17 Síntesis
P18 Certificación
P19 Handoff LaTeX
```

No combinar más de dos prompts de implementación en una sola sesión.

---

# 28. Prompt final de auditoría global

```text
Realiza una auditoría read-only de Closure V2.

Autoridades:
- thesis-closure-v1 debe seguir inmutable;
- thesis-closure-v2 es el candidato de cierre.

Verifica:
1. ancestry y tags;
2. scopes V1/V2;
3. protocol before outcomes;
4. complete-case y denominadores;
5. shared-fit P0/P1;
6. 5/5 slots;
7. calibration before evaluation;
8. fresh/posthoc labels;
9. metrics y estimands separados;
10. bootstrap por ubicación;
11. Holm completo;
12. degradación;
13. planificación;
14. claim matrix;
15. DVC;
16. tests/OpenAPI/E2E;
17. secretos;
18. manifests-last;
19. correspondence claim→artifact→metric→denominator→limitation.

No modifiques archivos.
Entrega un reporte con:
- PASS;
- FAIL;
- WARNING;
- path y evidencia exacta;
- bloqueadores para actualizar la tesis.
```

---

# 29. Lenguaje permitido después de V2

### Si P1 es evaluable

```text
La rama temporal P1 fue ajustada bajo una política preespecificada de casos
completos que conservó las secuencias no elegibles en el ledger de
disponibilidad.
```

### Si P1 mejora en fresh-primary

```text
En la superficie fresca especificada, P1 mostró una diferencia favorable en
[metric] frente a [reference], con [IC], bajo [estimand], [horizon] y
[availability].
```

### Si sólo mejora post hoc

```text
En el análisis retrospectivo complementario sobre el holdout previamente
abierto de Closure V1, P1 mostró...
```

### Si no mejora

```text
P1 fue técnicamente evaluable, pero no mostró una ventaja consistente frente a
B2/P0; este resultado delimita el aporte de la complejidad temporal adaptativa
en la cohorte estudiada.
```

### Siempre prohibido sin evidencia adicional

```text
P1 es universalmente superior.
La evaluación es externa.
Se validó en cuerpos de agua nuevos.
La planificación demuestra causalidad.
El sistema recomienda intervenciones reales.
```

---

# 30. Conclusión operativa

El cambio esencial de `Closure V2` no consiste en eliminar 488 filas. Consiste en definir antes de la ejecución una población de ajuste elegible, mantener la población intentada completa, comparar P0/P1 sobre soporte común, auditar el sesgo de elegibilidad y separar calidad predictiva de disponibilidad operacional.

La ejecución será científicamente útil aunque P1 no gane. El resultado mínimo valioso es:

```text
P1 fue ajustado, evaluado y comparado con reglas predeclaradas;
la evidencia muestra dónde aporta, dónde no aporta y bajo qué disponibilidad.
```

La ejecución será confirmatoria sólo si existe una superficie fresca que no haya influido en el diseño del modelo. Si sólo se reutiliza el holdout V1, V2 sigue siendo una mejora importante del cierre empírico, pero debe presentarse como análisis retrospectivo complementario.

El repositorio estará listo para actualizar la tesis cuando todas las afirmaciones nuevas puedan recorrer esta cadena:

```text
claim
→ cohort
→ estimand
→ denominator
→ artifact
→ metric
→ uncertainty
→ authority commit
→ limitation
```

Ese es el criterio final de aceptación.

---

## 31. Fuentes auditadas para esta guía

### Fuentes institucionales y del proyecto

- `251110_Protocolo_Investigacion.pdf`.
- `SOLICITUD_MODIFICACION_PROTOCOLO_.docx`.
- `RubricaDoctorado.pdf`.
- `CIERRE_FASES_1_2_3_4.md`.
- `PROYECTO_COMPLETO.md`.

### Fuentes públicas del repositorio

- tag `thesis-closure-v1`.
- `README.md`.
- `configs/closure_v1/analysis_plan.yaml`.
- `configs/closure_v1/model_benchmark.yaml`.
- `configs/closure_v1/development_runtime.yaml`.
- `src/experiments/train_closure_pipe.py`.
- `reports/closure_v1/02_models/P0/seed_1729_manifest.json`.
- `reports/closure_v1/02_models/P1/seed_1729_manifest.json`.
- `reports/closure_v1/11_synthesis/FINAL_CLOSURE_REPORT.md`.
- `reports/closure_v1/11_synthesis/THESIS_CLAIM_EVIDENCE_MATRIX.csv`.
- `reports/closure_v1/12_certification/FINAL_DOCTORAL_CERTIFICATION_REPORT.md`.

### Límites

Esta guía define un protocolo nuevo. Los umbrales V2, el perfil de entrenamiento de 512/60/10 y la jerarquía de cohorte fresca son recomendaciones metodológicas preespecificadas en este documento; no son resultados ya observados. Deben revisarse y bloquearse antes de ejecutar V2.
