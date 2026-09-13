# ESMA — MiCA Register

Contrato: `fixtures/contracts/esma-mica-register.json`

- **Qué acredita**: CASPs autorizados (y emisores de criptoactivos) con Estado miembro de
  origen y pasaportes (H7: verificar alcance exacto, arts. 107/109 MiCA).
- **Rol en identidad (G0.2)**: fuente portadora de identificadores. Ante la falta de NIF/LEI
  en el listado CNMV (H2), la identidad MiCA se resuelve aquí (adopción W6 con candidato
  único) o en la autoridad home-state.
- **Cobertura con UNKNOWN deliberado**: no hay regla para `CREDIT_INSTITUTION`. Las entidades
  financieras que prestan CAS mediante notificación (H1) no quedan ni cubiertas ni excluidas;
  sus positivos exigen aserción con evidencia directa (fixture asm-003). Esto evita inferir
  mecanismos jurídicos que H1 aún no ha verificado.
- **Territorialidad**: si el registro no distingue sucursal vs. FPS en pasaportes (H7), el
  `territorial_basis` de sus aserciones es `OTHER` con flag, nunca inventado.
- **Negativos**: `EXPLICIT_NEGATIVE_ONLY`; la ausencia no es negativa (lag de feeds).
