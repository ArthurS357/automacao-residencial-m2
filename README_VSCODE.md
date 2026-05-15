# Automacao Residencial M2 - Wokwi + MicroPython + VS Code

Este pacote foi ajustado para rodar no Wokwi for VS Code com ESP32 e MicroPython.

## Problema corrigido

No Wokwi Web, o `main.py` costuma ser enviado junto com o projeto. No Wokwi for VS Code, o simulador inicializa o firmware MicroPython e abre o REPL, mas os arquivos locais precisam ser enviados para o filesystem do MicroPython.

Este pacote inclui um uploader proprio em Python que usa a porta RFC2217 do Wokwi (`localhost:4000`) e envia os arquivos pelo REPL amigavel do MicroPython. Ele nao depende do modo `raw REPL` do `mpremote`, pois no seu ambiente o `mpremote` falhou com:

```text
mpremote.transport.TransportError: could not enter raw repl
```

A versao v3 tambem corrige este erro do `pyserial`:

```text
write_timeout is currently not supported
```

A correcao foi remover `write_timeout` da abertura da conexao RFC2217.

## Arquivos importantes

```text
main.py                              Codigo MicroPython principal
config.py                            Configuracoes de WiFi, MQTT, HTTP e automacao
boot.py                              Mensagem de boot
ssd1306.py                           Driver OLED
umqtt/simple.py                      Cliente MQTT ajustado
wokwi.toml                           Configuracao Wokwi VS Code
tools/upload_wokwi_micropython.py    Entrada principal do uploader
tools/upload_serial_repl.py          Uploader via REPL amigavel/RFC2217
tools/diagnose_wokwi.py              Diagnostico rapido
upload.ps1                           Atalho PowerShell
upload.cmd                           Atalho CMD
requirements-dev.txt                 Dependencias locais
```

## 1. Abrir no VS Code

Abra exatamente a pasta abaixo no VS Code:

```text
automacao-residencial-m2-vscode
```

Nao abra apenas o ZIP e nao abra a pasta acima dela.

## 2. Instalar dependencias

No terminal do VS Code:

```powershell
python -m pip install -r requirements-dev.txt
```

## 3. Iniciar o simulador

1. Abra `diagram.json`.
2. Pressione `Ctrl+Shift+P`.
3. Execute:

```text
Wokwi: Start Simulator
```

4. Mantenha a aba do simulador Wokwi visivel.

## 4. Enviar os arquivos para o MicroPython

Use:

```powershell
powershell -ExecutionPolicy Bypass -File .\upload.ps1
```

Alternativas:

```cmd
upload.cmd
```

ou:

```powershell
python tools/upload_wokwi_micropython.py
```

## 5. Verificar arquivos no ESP32 simulado

```powershell
python tools/upload_wokwi_micropython.py --list-only
```

Saida esperada aproximada:

```text
/ ['boot.py', 'config.py', 'ssd1306.py', 'umqtt', 'main.py']
/umqtt ['__init__.py', 'simple.py']
```

## 6. Se ainda falhar

Rode o diagnostico:

```powershell
python tools/diagnose_wokwi.py
```

Depois tente o modo mais lento, que usa `exec(...)` linha a linha em vez de paste mode:

```powershell
python tools/upload_wokwi_micropython.py --method exec --chunk-size 192
```

Ou via PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\upload.ps1 --method exec --chunk-size 192
```

Outras acoes uteis:

1. Clique na aba do simulador Wokwi para manter a simulacao ativa.
2. Execute `Wokwi: Stop Simulator`.
3. Execute `Wokwi: Start Simulator`.
4. Rode novamente o upload.

## 7. Dashboard HTTP

Depois que o terminal mostrar que o WiFi conectou e o servidor HTTP iniciou, acesse:

```text
http://localhost:8180
```

O redirecionamento esta em `wokwi.toml`:

```toml
[[net.forward]]
from = "localhost:8180"
to = "target:80"
```

## 8. MQTT

O projeto usa por padrao:

```text
broker.hivemq.com
topico de publicacao: casa/data
comandos:
  casa/cmd/led
  casa/cmd/relay
  casa/cmd/rele
  casa/cmd/buzzer
  casa/cmd/servo
  casa/cmd/auto
```

Exemplos de payload:

```text
on
off
true
false
90
```

## 9. Observacao sobre tokens

O token Blynk foi deixado como placeholder em `config.py`. Nao coloque token real em repositorio publico.
