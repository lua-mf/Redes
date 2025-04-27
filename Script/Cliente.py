import socket
import threading
from time import sleep

def calcular_checksum(pacote):
    return sum(ord(char) for char in pacote) % 256

HOST = '127.0.0.1'
PORT = 50000

# Configuração inicial - solicita ao usuário
print("Selecione o modo de operação:")
print("1 - Go-Back-N")
print("2 - Repetição Seletiva")

while True:
    try:
        modo_operacao = int(input("Digite o número do modo (1 ou 2): "))
        if modo_operacao in [1, 2]:
            break
        else:
            print("Modo inválido. Digite 1 ou 2.")
    except ValueError:
        print("Entrada inválida. Digite apenas números.")

while True:
    try:
        tamanho_max = int(input("Digite o tamanho máximo do pacote (1 a 3): "))
        if 1 <= tamanho_max <= 3:
            break
        else:
            print("Tamanho inválido. Digite um número entre 1 e 3.")
    except ValueError:
        print("Entrada inválida. Digite apenas números.")

print("\nSelecione o modo de envio:")
print("1 - Individual")
print("2 - Lote")

while True:
    try:
        modo_envio = int(input("Digite o número do modo de envio (1 ou 2): "))
        if modo_envio in [1, 2]:
            break
        else:
            print("Modo inválido. Digite 1 ou 2.")
    except ValueError:
        print("Entrada inválida. Digite apenas números.")

# Cliente digita a mensagem completa
mensagem = input("\nDigite a mensagem completa para enviar: ")

# Divide a mensagem em pacotes conforme tamanho_max
pacotes = [mensagem[i:i+tamanho_max] for i in range(0, len(mensagem), tamanho_max)]
qtd_pacotes = len(pacotes)

# Criação do socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)

timers = {}  # Dicionário para guardar temporizadores

def enviar_pacote(idx, pacote):
    def timeout():
        print(f"[TIMEOUT] Sem resposta para o pacote {idx}. Reenviando...")
        enviar_pacote(idx, pacote)  # Reenvia o mesmo pacote

    checksum = calcular_checksum(pacote)
    pacote_enviado = f"{checksum:03d}|{pacote}"
    try:
        s.sendall(pacote_enviado.encode())
        print(f"Pacote {idx} enviado: '{pacote_enviado}'")
    except Exception as e:
        print(f"Erro ao enviar pacote {idx}: {e}")
        return

    # Inicia o temporizador para este pacote
    timer = threading.Timer(2.0, timeout)
    timer.start()
    timers[idx] = timer

try:
    s.connect((HOST, PORT))
    print(f"\nConectado ao servidor {HOST}:{PORT}")
    
    # Envia handshake
    mensagem_handshake = f"modo={modo_operacao},tamanho={tamanho_max},envio={modo_envio},qtd_pacotes={qtd_pacotes}"
    s.sendall(mensagem_handshake.encode())
    
    resposta = s.recv(1024).decode()
    
    if resposta == "handshake_ok":
        print("Handshake concluído com sucesso.\n")
        
        if modo_envio == 1:
            print("Enviando em modo INDIVIDUAL...\n")
            for idx, pacote in enumerate(pacotes, 1):
                enviar_pacote(idx, pacote)

                while True:
                    try:
                        resposta = s.recv(1024).decode()
                        if resposta.startswith("ack|"):
                            numero_pacote = int(resposta.split("|")[1])
                            print(f"[ACK] Pacote {numero_pacote} confirmado.")
                            timers[numero_pacote].cancel()
                            break
                        elif resposta.startswith("nack|"):
                            numero_pacote = int(resposta.split("|")[1])
                            print(f"[NACK] Erro no pacote {numero_pacote}, reenviando...")
                            timers[numero_pacote].cancel()
                            enviar_pacote(numero_pacote, pacotes[numero_pacote-1])
                    except socket.timeout:
                        continue
                if idx < len(pacotes):
                    sleep(1)

        else:
            print("Modo LOTE ainda não implementado para temporizador individual.\n")
        print("\nTodos os pacotes foram enviados e confirmados.")
    else:
        print(f"Resposta inesperada do servidor: {resposta}")

except Exception as e:
    print(f"Ocorreu um erro: {e}")
finally:
    for t in timers.values():
        t.cancel()
    s.close()
    print("Conexão fechada.")