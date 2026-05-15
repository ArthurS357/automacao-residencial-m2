# Automação Residencial M2 — Wokwi + ESP32 + MicroPython

Última atualização: 2026-05-15

Projeto de automação residencial executado em **ESP32 simulado no Wokwi for VS Code**, usando **MicroPython**, sensores virtuais, atuadores, dashboard HTTP local e publicação/recebimento de comandos via MQTT.

Este README descreve a forma correta de preparar, executar, reenviar o código para o ESP32 simulado e diagnosticar falhas comuns no VS Code.

---

## 1. Visão geral

O sistema simula uma automação residencial com:

- Leitura de temperatura e umidade pelo DHT22;
- Detecção de movimento por PIR;
- Leitura de luminosidade por LDR;
- Medição de distância pelo HC-SR04;
- Exibição local em OLED SSD1306;
- Controle de LED, relé, buzzer e servo;
- Dashboard HTTP acessível pelo navegador;
- Publicação de telemetria em MQTT;
- Recebimento de comandos MQTT para controle remoto;
- Modo automático baseado em luminosidade, movimento e temperatura.

No Wokwi for VS Code, o simulador inicia o firmware MicroPython e abre o REPL. O código local do projeto precisa ser enviado para o filesystem MicroPython do ESP32 simulado antes de executar. Por isso este projeto inclui um uploader próprio em Python.

---

## 2. Requisitos

### Software local

- Visual Studio Code;
- Extensão **Wokwi for VS Code** instalada e ativada;
- Python local instalado, preferencialmente Python 3.13 ou superior;
- `pip` disponível no terminal;
- Acesso à internet para o Wokwi, WiFi virtual e MQTT público.

### Dependências Python locais

As dependências ficam em `requirements-dev.txt`:

```text
pyserial==3.5
mpremote==1.28.0
```

Instale com:

```powershell
python -m pip install -r requirements-dev.txt
```

Observação: o upload recomendado deste projeto usa `pyserial` via RFC2217. O `mpremote` permanece instalado por compatibilidade, diagnóstico e aderência ao fluxo MicroPython/Wokwi, mas não é o método principal de upload neste projeto.

---

## 3. Estrutura do projeto

```text
automacao-residencial-m2-vscode/
├── .vscode/
│   ├── extensions.json
│   └── tasks.json
├── boot.py
├── config.py
├── dashboard.PNG
├── diagram.json
├── esp32-firmware.bin
├── flow.PNG
├── main.py
├── README.md
├── README_VSCODE.md
├── requirements-dev.txt
├── sketch.ino
├── ssd1306.py
├── tools/
│   ├── diagnose_wokwi.py
│   ├── upload_serial_repl.py
│   └── upload_wokwi_micropython.py
├── umqtt/
│   ├── __init__.py
│   └── simple.py
├── upload.cmd
├── upload.ps1
├── wokwi-project.txt
└── wokwi.toml
```

### Arquivos principais

| Arquivo | Função |
|---|---|
| `main.py` | Aplicação MicroPython principal. Lê sensores, aplica automação, publica MQTT e serve o dashboard HTTP. |
| `config.py` | Configura WiFi, MQTT, intervalos, limites de automação e token placeholder. |
| `boot.py` | Executado antes do `main.py` no MicroPython. Mantido simples para facilitar diagnóstico. |
| `diagram.json` | Circuito do Wokwi com ESP32, sensores e atuadores. |
| `wokwi.toml` | Configuração do Wokwi for VS Code, firmware, porta RFC2217 e redirecionamento HTTP. |
| `ssd1306.py` | Driver OLED usado pelo MicroPython. |
| `umqtt/simple.py` | Cliente MQTT ajustado para o projeto. |
| `tools/upload_wokwi_micropython.py` | Entrada principal do uploader. |
| `tools/upload_serial_repl.py` | Implementação do upload via REPL amigável/RFC2217. |
| `tools/diagnose_wokwi.py` | Diagnóstico rápido da porta, pyserial e conexão serial. |
| `upload.ps1` | Atalho PowerShell para upload. |
| `upload.cmd` | Atalho CMD para upload. |
| `sketch.ino` | Arquivo legado do projeto Wokwi original. Não é usado na execução MicroPython. |

---

## 4. Pinagem do circuito

A pinagem está sincronizada entre `main.py` e `diagram.json`.

| Componente | Pino ESP32 |
|---|---:|
| DHT22 | GPIO 15 |
| PIR | GPIO 13 |
| LDR / Fotoresistor AO | GPIO 34 |
| HC-SR04 TRIG | GPIO 5 |
| HC-SR04 ECHO | GPIO 18 |
| LED | GPIO 2 |
| Relé | GPIO 4 |
| Buzzer | GPIO 14 |
| Servo PWM | GPIO 12 |
| OLED SDA | GPIO 21 |
| OLED SCL | GPIO 22 |

---

## 5. Configuração do Wokwi

O arquivo `wokwi.toml` deve conter:

```toml
[wokwi]
version = 1
firmware = "esp32-firmware.bin"
rfc2217ServerPort = 4000

[[net.forward]]
from = "localhost:8180"
to = "target:80"
```

### O que essa configuração faz

- `firmware = "esp32-firmware.bin"` define o firmware MicroPython do ESP32 simulado.
- `rfc2217ServerPort = 4000` expõe a serial do ESP32 simulado em `localhost:4000`.
- `[[net.forward]]` encaminha o servidor HTTP do ESP32, porta 80, para o computador local em `http://localhost:8180`.

---

## 6. Configuração da aplicação

As principais configurações ficam em `config.py`.

```python
WIFI_SSID = "Wokwi-GUEST"
WIFI_PASSWORD = ""

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC_PREFIX = "casa"
MQTT_TOPIC_PUB = "casa/data"
MQTT_CLIENT_ID = "esp32_smart_home_m2"

HTTP_PORT = 80

READ_INTERVAL_MS = 2000
MQTT_INTERVAL_MS = 5000
MQTT_RECONNECT_MS = 10000

LDR_DARK_THRESHOLD = 1800
TEMP_RELAY_THRESHOLD_C = 28
AUTO_MODE_DEFAULT = True

BLYNK_AUTH_TOKEN = "SUBSTITUA_PELO_TOKEN_DO_BLYNK_SE_FOR_USAR"
```

### Ajustes comuns

| Configuração | Quando alterar |
|---|---|
| `LDR_DARK_THRESHOLD` | Ajuste se o LED/buzzer ligarem ou desligarem em luminosidade inadequada. |
| `TEMP_RELAY_THRESHOLD_C` | Ajuste o limite de temperatura para acionar o relé automaticamente. |
| `MQTT_TOPIC_PREFIX` | Altere se quiser isolar os tópicos MQTT do seu projeto. |
| `MQTT_CLIENT_ID` | Altere se houver colisão de clientes MQTT no broker. |
| `BLYNK_AUTH_TOKEN` | Use somente se integrar Blynk. Não publique token real. |

---

## 7. Execução correta no VS Code

### 7.1 Abrir a pasta correta

Abra exatamente a pasta do projeto no VS Code:

```text
automacao-residencial-m2-vscode
```

Não abra apenas o arquivo ZIP e não abra uma pasta acima dela. O VS Code precisa enxergar `diagram.json`, `wokwi.toml`, `main.py` e a pasta `tools/` na raiz do workspace.

### 7.2 Instalar dependências

No terminal integrado do VS Code:

```powershell
python -m pip install -r requirements-dev.txt
```

### 7.3 Iniciar o simulador Wokwi

1. Abra o arquivo `diagram.json`;
2. Pressione `Ctrl+Shift+P`;
3. Execute:

```text
Wokwi: Start Simulator
```

4. Mantenha a aba do simulador Wokwi visível.

A aba do simulador precisa permanecer visível porque a simulação pode pausar quando a aba não está ativa/visível, o que pode interromper a saída serial e o upload.

### 7.4 Enviar os arquivos para o ESP32 simulado

Com o simulador rodando, abra outro terminal no VS Code e execute:

```powershell
powershell -ExecutionPolicy Bypass -File .\upload.ps1
```

Alternativa no CMD:

```cmd
upload.cmd
```

Alternativa direta pelo Python:

```powershell
python tools/upload_wokwi_micropython.py
```

### 7.5 O que o upload faz

O uploader envia estes arquivos para o filesystem MicroPython do ESP32 simulado:

```text
boot.py
config.py
ssd1306.py
umqtt/__init__.py
umqtt/simple.py
main.py
```

Depois do envio, ele faz um soft reset para o MicroPython carregar `boot.py` e executar `main.py`.

### 7.6 Saída esperada

No terminal do upload, a saída esperada é parecida com:

```text
Simulator found at localhost:4000 (attempt 1).
Connecting to MicroPython friendly REPL through pyserial/RFC2217...
REPL ready.
Execution method: paste
Uploading project files...

OK  boot.py -> /boot.py
OK  config.py -> /config.py
OK  ssd1306.py -> /ssd1306.py
OK  umqtt/__init__.py -> /umqtt/__init__.py
OK  umqtt/simple.py -> /umqtt/simple.py
OK  main.py -> /main.py

Files currently stored in MicroPython:
/ ['boot.py', 'config.py', 'ssd1306.py', 'umqtt', 'main.py']
/umqtt ['__init__.py', 'simple.py']

Resetting MicroPython to run main.py...
Upload finished.
```

No terminal serial do Wokwi, a saída esperada é parecida com:

```text
boot.py: Automacao Residencial M2
Iniciando Automacao Residencial M2...
Conectando ao WiFi 'Wokwi-GUEST'...
WiFi conectado: ...
Servidor HTTP pronto na porta 80.
MQTT conectado: broker.hivemq.com
STATUS: {...}
```

---

## 8. Execução por tarefa do VS Code

Também é possível executar pelo menu de tarefas:

1. Pressione `Ctrl+Shift+P`;
2. Execute:

```text
Tasks: Run Task
```

3. Escolha uma das tarefas:

| Tarefa | Uso |
|---|---|
| `Wokwi MicroPython: upload e reset (recomendado)` | Envia arquivos e reinicia o MicroPython. |
| `Wokwi MicroPython: upload lento fallback exec` | Usa método mais lento quando o upload normal falha. |
| `Wokwi MicroPython: listar arquivos remotos` | Lista arquivos no filesystem MicroPython. |
| `Wokwi MicroPython: diagnostico` | Verifica ambiente, porta e conexão RFC2217. |

---

## 9. Verificar arquivos enviados

Para listar os arquivos que estão no ESP32 simulado:

```powershell
python tools/upload_wokwi_micropython.py --list-only
```

Saída esperada:

```text
/ ['boot.py', 'config.py', 'ssd1306.py', 'umqtt', 'main.py']
/umqtt ['__init__.py', 'simple.py']
```

---

## 10. Reenviar após alterações

Sempre que alterar qualquer um destes arquivos:

```text
boot.py
config.py
ssd1306.py
umqtt/__init__.py
umqtt/simple.py
main.py
```

execute novamente:

```powershell
powershell -ExecutionPolicy Bypass -File .\upload.ps1
```

ou:

```powershell
python tools/upload_wokwi_micropython.py
```

O Wokwi for VS Code não puxa automaticamente as alterações locais do `main.py` para o filesystem MicroPython. É necessário reenviar.

Também é necessário reenviar os arquivos se você parar a simulação ou fechar a janela do simulador, pois o filesystem do MicroPython no simulador não é persistente.

---

## 11. Dashboard HTTP

Depois que aparecer no terminal serial:

```text
WiFi conectado: ...
Servidor HTTP pronto na porta 80.
```

acesse no navegador:

```text
http://localhost:8180
```

### Rotas disponíveis

| Rota | Função |
|---|---|
| `/` | Dashboard HTML. |
| `/api/status` | Retorna o estado atual em JSON. |
| `/led/on` | Liga LED e desativa modo automático. |
| `/led/off` | Desliga LED e desativa modo automático. |
| `/rele/on` | Liga relé e desativa modo automático. |
| `/rele/off` | Desliga relé e desativa modo automático. |
| `/buzzer/on` | Liga buzzer e desativa modo automático. |
| `/buzzer/off` | Desliga buzzer e desativa modo automático. |
| `/auto/on` | Ativa modo automático. |
| `/auto/off` | Desativa modo automático. |
| `/servo/0` | Move servo para 0 graus. |
| `/servo/90` | Move servo para 90 graus. |
| `/servo/180` | Move servo para 180 graus. |

### Teste rápido da API JSON

No navegador:

```text
http://localhost:8180/api/status
```

No PowerShell:

```powershell
Invoke-RestMethod http://localhost:8180/api/status
```

---

## 12. MQTT

### Broker padrão

```text
broker.hivemq.com
```

### Publicação de telemetria

O ESP32 publica o estado do sistema em:

```text
casa/data
```

Payload exemplo:

```json
{
  "temp": 25.5,
  "humidity": 60.0,
  "distance_cm": 123.4,
  "light": 1700,
  "motion": true,
  "led": 1,
  "relay": 0,
  "buzzer": 1,
  "servo_angle": 90,
  "auto_mode": true,
  "wifi_ip": "10.10.0.2",
  "mqtt": "online",
  "uptime_ms": 123456,
  "last_error": ""
}
```

### Tópicos de comando

| Tópico | Payload aceito | Ação |
|---|---|---|
| `casa/cmd/led` | `on`, `off`, `true`, `false`, `1`, `0` | Controla LED. |
| `casa/cmd/relay` | `on`, `off`, `true`, `false`, `1`, `0` | Controla relé. |
| `casa/cmd/rele` | `on`, `off`, `true`, `false`, `1`, `0` | Controla relé. |
| `casa/cmd/buzzer` | `on`, `off`, `true`, `false`, `1`, `0` | Controla buzzer. |
| `casa/cmd/servo` | `0` a `180` | Move o servo. |
| `casa/cmd/auto` | `on`, `off`, `true`, `false`, `1`, `0` | Liga/desliga modo automático. |

Também há compatibilidade com tópicos legados:

```text
casa/led
casa/rele
casa/buzzer
casa/servo
```

### Exemplo com mosquitto_pub

Se tiver o Mosquitto instalado localmente:

```powershell
mosquitto_pub -h broker.hivemq.com -t casa/cmd/led -m on
mosquitto_pub -h broker.hivemq.com -t casa/cmd/servo -m 90
mosquitto_pub -h broker.hivemq.com -t casa/cmd/auto -m on
```

---

## 13. Lógica do modo automático

Quando `AUTO_MODE_DEFAULT = True` ou o modo automático está ativado:

| Condição | Ação |
|---|---|
| Ambiente escuro e movimento detectado | Liga LED e buzzer. |
| Temperatura maior ou igual a `TEMP_RELAY_THRESHOLD_C` | Liga o relé. |
| Sem condição de acionamento | Desliga saídas controladas automaticamente. |

Se LED, relé ou buzzer forem acionados manualmente pelo dashboard ou MQTT, o sistema desativa o modo automático para respeitar o comando manual. Para voltar ao modo automático, use:

```text
http://localhost:8180/auto/on
```

ou publique MQTT:

```text
Tópico: casa/cmd/auto
Payload: on
```

---

## 14. Diagnóstico

### Diagnóstico rápido

Com o simulador rodando:

```powershell
python tools/diagnose_wokwi.py
```

Esse comando verifica:

- Versão do Python local;
- Executável Python em uso;
- Instalação do `pyserial`;
- Abertura da porta TCP `localhost:4000`;
- Abertura da serial RFC2217;
- Prévia da saída serial do MicroPython.

### Upload lento de contingência

Se o upload padrão falhar, use o modo mais lento:

```powershell
python tools/upload_wokwi_micropython.py --method exec --chunk-size 192
```

Use essa opção principalmente se o paste mode não responder corretamente no seu ambiente.

---

## 15. Solução de problemas

| Sintoma | Causa provável | Correção |
|---|---|---|
| O terminal abre em `>>>`, mas o código não roda | Arquivos locais ainda não foram enviados para o filesystem MicroPython | Execute `powershell -ExecutionPolicy Bypass -File .\upload.ps1`. |
| `could not enter raw repl` ao usar `mpremote` | `mpremote` não conseguiu entrar no raw REPL | Use o uploader do projeto: `python tools/upload_wokwi_micropython.py`. |
| `write_timeout is currently not supported` | Uso de `write_timeout` com backend RFC2217 do pyserial | Use a versão corrigida do uploader v3 ou posterior. |
| `Wokwi did not answer at localhost:4000` | Simulador parado, aba não visível, porta errada ou `wokwi.toml` incorreto | Inicie o simulador, mantenha a aba visível e confirme `rfc2217ServerPort = 4000`. |
| Dashboard não abre em `localhost:8180` | WiFi/HTTP ainda não iniciou ou redirecionamento ausente | Aguarde `Servidor HTTP pronto`, confirme `[[net.forward]]` em `wokwi.toml` e tente novamente. |
| MQTT fica `offline` | Broker indisponível, rede instável ou cliente duplicado | Aguarde reconexão, altere `MQTT_CLIENT_ID` ou teste outro broker. |
| Alterei `main.py`, mas nada mudou | Código alterado não foi reenviado | Rode o upload novamente. |
| Arquivos somem após parar o simulador | Filesystem do simulador não é persistente | Inicie novamente o Wokwi e rode o upload de novo. |
| OLED não mostra dados | Erro de I2C ou driver | Verifique pinos SDA/SCL e arquivo `ssd1306.py`. |
| Sensor ultrassônico retorna `None` | Timeout de leitura do HC-SR04 | Ajuste distância no simulador e observe o log serial. |

---

## 16. Comandos úteis

### Instalar dependências

```powershell
python -m pip install -r requirements-dev.txt
```

### Iniciar upload recomendado

```powershell
powershell -ExecutionPolicy Bypass -File .\upload.ps1
```

### Upload direto pelo Python

```powershell
python tools/upload_wokwi_micropython.py
```

### Upload sem reset

```powershell
python tools/upload_wokwi_micropython.py --no-reset
```

### Upload lento

```powershell
python tools/upload_wokwi_micropython.py --method exec --chunk-size 192
```

### Listar arquivos remotos

```powershell
python tools/upload_wokwi_micropython.py --list-only
```

### Diagnosticar conexão Wokwi

```powershell
python tools/diagnose_wokwi.py
```

### Consultar API local

```powershell
Invoke-RestMethod http://localhost:8180/api/status
```

---

## 17. Fluxo recomendado de desenvolvimento

Use este fluxo sempre que for desenvolver ou apresentar o projeto:

1. Abrir a pasta `automacao-residencial-m2-vscode` no VS Code;
2. Abrir `diagram.json`;
3. Executar `Wokwi: Start Simulator`;
4. Manter a aba do simulador visível;
5. Rodar:

```powershell
powershell -ExecutionPolicy Bypass -File .\upload.ps1
```

6. Aguardar o terminal serial mostrar:

```text
WiFi conectado
Servidor HTTP pronto
STATUS
```

7. Abrir:

```text
http://localhost:8180
```

8. Alterou código? Salvar e repetir o upload;
9. Parou/fechou o simulador? Iniciar novamente e repetir o upload.

---

## 18. O que não fazer

Não execute o `main.py` com CPython local:

```powershell
python main.py
```

Esse arquivo foi feito para MicroPython no ESP32 e depende de módulos como:

```text
machine
network
dht
```

Esses módulos existem no firmware MicroPython, não no Python local do computador.

Também não use o comando abaixo como fluxo principal neste projeto, pois no ambiente testado ele falhou ao entrar no raw REPL:

```powershell
python -m mpremote connect port:rfc2217://localhost:4000 fs tree :
```

Use o uploader próprio:

```powershell
python tools/upload_wokwi_micropython.py
```

---

## 19. Segurança e boas práticas

- Não coloque token real do Blynk, senhas ou chaves de API em repositório público.
- O broker `broker.hivemq.com` é público; use apenas para demonstração, testes e laboratório.
- Para ambiente real, use broker MQTT autenticado, TLS e tópicos segregados por dispositivo/ambiente.
- Registre evidências de execução pelo log serial do Wokwi e pelas respostas de `/api/status`.
- Mantenha `requirements-dev.txt` versionado para reprodutibilidade.
- Antes de portar para hardware físico, revise alimentação, níveis lógicos, corrente dos atuadores e proteção elétrica.
- Para auditoria ou demonstração controlada, registre:
  - versão do firmware;
  - versão do pacote;
  - saída do upload;
  - saída do diagnóstico;
  - print do dashboard;
  - payload JSON de `/api/status`.

---

## 20. Referências técnicas

- Wokwi for VS Code — Getting Started: https://docs.wokwi.com/vscode/getting-started
- Wokwi for VS Code — MicroPython projects: https://docs.wokwi.com/vscode/vscode-micropython
- Wokwi for VS Code — Project configuration / `wokwi.toml`: https://docs.wokwi.com/vscode/project-config
- MicroPython — REPL, paste mode, raw REPL e soft reset: https://docs.micropython.org/en/latest/reference/repl.html

---

## 21. Checklist final de execução

Antes de considerar o sistema funcionando, valide:

- [ ] A pasta correta foi aberta no VS Code;
- [ ] `requirements-dev.txt` foi instalado;
- [ ] `diagram.json` foi aberto;
- [ ] `Wokwi: Start Simulator` foi executado;
- [ ] A aba do simulador ficou visível;
- [ ] `upload.ps1` ou `tools/upload_wokwi_micropython.py` executou sem erro;
- [ ] O terminal serial exibiu `boot.py`;
- [ ] O terminal serial exibiu `Iniciando Automacao Residencial M2`;
- [ ] O WiFi conectou;
- [ ] O servidor HTTP iniciou;
- [ ] `http://localhost:8180` abriu;
- [ ] `http://localhost:8180/api/status` retornou JSON;
- [ ] O dashboard controlou LED, relé, buzzer, servo e modo automático;
- [ ] O MQTT conectou ou, se estiver offline, o dashboard continuou funcionando.
