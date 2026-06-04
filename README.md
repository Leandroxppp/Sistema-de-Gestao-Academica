# Sistema de Gestao do Desempenho Estudantil - Backend

Backend REST em Python para acompanhamento de desempenho academico, classificacao de risco, alertas e relatorios para professores e gestores.

O projeto usa apenas a biblioteca padrao do Python e SQLite, portanto nao exige instalacao de dependencias externas.

## Funcionalidades

- Autenticacao de usuarios com perfil `professor` ou `gestor`.
- Cadastro de usuarios, alunos e materias.
- Vinculo de alunos a materias.
- Registro de desempenho academico com notas, frequencia e atividades entregues.
- Motor de analise de risco por regras.
- Dashboard com indicadores consolidados.
- Alertas para alunos em risco medio ou alto.
- Geracao e consulta de relatorios.
- Testes automatizados com `unittest`.

## Perfis de Acesso

### Gestor

Pode:

- cadastrar usuarios;
- cadastrar alunos;
- cadastrar materias;
- vincular alunos a materias;
- consultar dashboard, alunos, alertas e relatorios;
- registrar desempenho;
- recalcular analises de risco.

### Professor

Pode:

- consultar dashboard, alunos, alertas e relatorios;
- registrar desempenho dos alunos;
- gerar relatorios.

Nao pode:

- cadastrar alunos;
- cadastrar materias;
- cadastrar usuarios;
- vincular alunos a materias.

## Requisitos

- Python 3.10 ou superior.

## Como Executar

No terminal:

```powershell
python .\run.py --host 127.0.0.1 --port 8000
```

Depois acesse:

```text
http://127.0.0.1:8000/
```

O banco SQLite sera criado automaticamente em `data/academico.db` com dados de demonstracao.

## Usuarios de Demonstracao

```text
professor@sigma.edu / professor123
gestor@sigma.edu / gestor123
```

## Fluxo Basico de Teste

### 1. Login como gestor

```powershell
$login = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/auth/login" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"email":"gestor@sigma.edu","senha":"gestor123"}'

$headers = @{ Authorization = "Bearer $($login.token)" }
```

### 2. Consultar dashboard

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/dashboard" `
  -Headers $headers
```

### 3. Registrar desempenho com atividades

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/alunos/1/desempenhos" `
  -Method POST `
  -Headers $headers `
  -ContentType "application/json" `
  -Body '{"materia_id":1,"notas":[8.0,8.5,9.0],"frequencia":95,"atividades_entregues":1,"atividades_esperadas":4}'
```

Resposta esperada, em formato resumido:

```json
{
  "analise": {
    "nivel": "Alto",
    "fator_risco": 0.2125,
    "media_notas": 8.5,
    "frequencia": 95.0,
    "atividades_entregues": 1,
    "atividades_esperadas": 4
  }
}
```

Nesse exemplo, o aluno pode ser classificado como `Alto` mesmo com boa media e frequencia, porque entregou menos de 50% das atividades esperadas.

## Endpoints

### Publicos

| Metodo | Rota | Descricao |
|---|---|---|
| GET | `/` | Informacoes iniciais da API |
| GET | `/health` | Verificacao de saude |
| POST | `/auth/login` | Login |

### Autenticados

| Metodo | Rota | Descricao |
|---|---|---|
| GET | `/usuarios` | Lista usuarios |
| POST | `/usuarios` | Cadastra usuario, somente gestor |
| GET | `/materias` | Lista materias |
| POST | `/materias` | Cadastra materia, somente gestor |
| GET | `/alunos` | Lista alunos |
| POST | `/alunos` | Cadastra aluno, somente gestor |
| GET | `/alunos/{aluno_id}` | Detalha aluno |
| POST | `/alunos/{aluno_id}/materias/{materia_id}` | Vincula aluno a materia, somente gestor |
| POST | `/alunos/{aluno_id}/desempenhos` | Registra desempenho |
| POST | `/analises/recalcular` | Recalcula riscos |
| GET | `/dashboard` | Consulta indicadores |
| GET | `/alertas` | Lista alertas |
| GET | `/relatorios` | Lista relatorios |
| POST | `/relatorios` | Cria relatorio |

## Motor de Analise de Risco

O motor usa regras deterministicas baseadas em:

- media das notas;
- frequencia;
- quantidade de atividades entregues;
- quantidade de atividades esperadas.

Campos aceitos no registro de desempenho:

```json
{
  "materia_id": 1,
  "notas": [7.0, 8.0, 6.5],
  "frequencia": 82,
  "atividades_entregues": 2,
  "atividades_esperadas": 3,
  "data_referencia": "2026-06-04"
}
```

`atividades_entregues` e `atividades_esperadas` sao opcionais. Quando nao forem enviados, o risco e calculado apenas com notas e frequencia.

Regras principais:

- risco alto: media menor que 5, frequencia menor que 65%, entrega de menos de 50% das atividades ou `fator_risco >= 0.70`;
- risco medio: media menor que 7, frequencia menor que 80%, entrega abaixo de 75% das atividades ou `fator_risco >= 0.40`;
- risco baixo: indicadores dentro dos limites esperados.

## Testes

Execute:

```powershell
python -m unittest discover -s tests
```

## Estrutura

```text
.
├── app
│   ├── api.py
│   ├── database.py
│   ├── models.py
│   └── services.py
├── tests
│   └── test_services.py
├── run.py
└── README.md
```
