# Backend - Sistema de Gestao do Desempenho Estudantil

Backend REST em Python para o projeto da Equipe Sigma. A implementacao segue os requisitos do plano e os diagramas em `../diagramas`, cobrindo autenticacao, dados academicos, motor de previsao por regras, dashboard, alertas e relatorios.

## Como executar

Requer Python 3.10+ e nao usa dependencias externas.

```powershell
cd coding
python .\run.py --host 127.0.0.1 --port 8000
```

O SQLite sera criado automaticamente em `coding/data/academico.db` com dados de demonstracao.

Usuarios iniciais:

- `professor@sigma.edu` / `professor123`
- `gestor@sigma.edu` / `gestor123`

## Fluxo basico

1. Fazer login em `POST /auth/login`.
2. Usar o token retornado no header `Authorization: Bearer <token>`.
3. Consultar `GET /dashboard`, `GET /alunos`, `GET /alertas` e `GET /relatorios`.
4. Registrar novos desempenhos em `POST /alunos/{id}/desempenhos`.
5. Reprocessar previsoes em `POST /analises/recalcular`.

## Endpoints

### Publicos

- `GET /health`
- `POST /auth/login`

Exemplo:

```json
{
  "email": "professor@sigma.edu",
  "senha": "professor123"
}
```

### Autenticados

- `GET /usuarios`
- `POST /usuarios`
- `GET /materias`
- `POST /materias`
- `GET /alunos`
- `POST /alunos`
- `GET /alunos/{aluno_id}`
- `POST /alunos/{aluno_id}/materias/{materia_id}`
- `POST /alunos/{aluno_id}/desempenhos`
- `POST /analises/recalcular`
- `GET /dashboard`
- `GET /alertas`
- `GET /relatorios`
- `POST /relatorios`

Exemplo de desempenho:

```json
{
  "materia_id": 1,
  "notas": [4.0, 5.5, 6.0],
  "frequencia": 68,
  "data_referencia": "2026-06-01"
}
```

## Regras do MotorIA

O `MotorIA` usa regras deterministicas, conforme a contingencia prevista no plano:

- risco alto: media menor que 5, frequencia menor que 65 ou probabilidade maior/igual a 0.70;
- risco medio: media menor que 7, frequencia menor que 80 ou probabilidade maior/igual a 0.40;
- risco baixo: indicadores dentro dos limites esperados.

Ao registrar desempenho, o backend salva a analise, atualiza o status do aluno e gera alerta para risco medio ou alto.

## Testes

```powershell
cd coding
python -m unittest discover -s tests
```
