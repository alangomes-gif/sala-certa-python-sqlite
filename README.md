# Sala Certa

Aplicação web local para equipes que compartilham salas: consultar agenda por data, reservar um espaço e cancelar reservas. Demonstração de portfólio com dados fictícios. Diferente de um analisador de agenda, mantém o ciclo de reservas no banco e bloqueia conflitos na gravação.

## Executar em dois minutos
Python 3.10 ou superior. Sem pacotes externos.

```powershell
python app.py
```
Abra http://127.0.0.1:8771 no navegador. Selecione uma data, sala, título, responsável fictício, intervalo e participantes. O banco reservas.db é criado na pasta do programa e preservado entre reinícios. Para outro banco: `python app.py --banco demo.db --porta 8772`.

```powershell
python -m unittest -v
```
Os testes usam bancos temporários e cobrem conflito, intervalo consecutivo, salas distintas, cancelamento, persistência, entradas inválidas, disputa entre duas threads e requisições HTTP reais.

## Exemplo de uso
Reserve Horizonte das 09h às 10h. Outra tentativa nessa sala das 09h30 às 10h30 recebe HTTP 409 e mensagem na tela. Uma reserva a partir das 10h ou na sala Jardim é permitida. Cancelar libera o intervalo.

## Organização e decisões
- `app.py`: regras, persistência SQLite e servidor HTTP JSON com biblioteca padrão.
- `index.html`: interface responsiva, formulário, agenda por sala, estados de sucesso/erro. Usa textContent para exibir conteúdo variável.
- `test_app.py`: testes de regras, concorrência e API.
- SQLite usa parâmetros nas consultas e `BEGIN IMMEDIATE` na checagem + inserção. Assim duas conexões não aprovam simultaneamente o mesmo intervalo.
- Horários usam formato ISO de minuto e o mesmo fuso local. Intervalos [início, fim): um encontro pode começar quando outro termina.
- Cancelamento é lógico; o registro permanece no banco, mas sai da agenda ativa.

## API
| Método | Rota | Resultado |
|---|---|---|
| GET | /api/salas | Catálogo com capacidade |
| GET | /api/reservas?dia=2026-11-05 | Reservas ativas da data |
| POST | /api/reservas | Cria; 201, 409 em conflito, 422 em dados inválidos |
| POST | /api/reservas/1/cancelar | Cancela; 404 se não ativa |

Corpo de criação:
```json
{"sala":1,"titulo":"Planejamento fictício","responsavel":"Equipe Aurora","inicio":"2026-11-05T09:00","fim":"2026-11-05T10:00","pessoas":4}
```

## Limites
Servidor de demonstração restrito a 127.0.0.1, sem autenticação ou autorização: qualquer pessoa com acesso local pode cancelar. Não exponha na internet. Não é uma implantação de produção. Não há recorrência, convites, integração com calendários, fusos múltiplos, auditoria de usuários ou restrição de datas passadas. Reservas no mesmo dia entre 08h e 19h. Catálogo fixo com três salas. Não use dados pessoais reais. O SQLite atende a demonstração local, não um cenário distribuído de alta escala.

As imagens de demonstração, quando presentes, mostram o programa real com dados fictícios. Nenhum resultado comercial é alegado.
