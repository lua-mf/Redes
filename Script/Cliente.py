import socket
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
try:
    s.connect((HOST, PORT))
    print(f"\nConectado ao servidor {HOST}:{PORT}")
    
    # Envia handshake com qtd_pacotes
    mensagem_handshake = f"modo={modo_operacao},tamanho={tamanho_max},envio={modo_envio},qtd_pacotes={qtd_pacotes}"
    s.sendall(mensagem_handshake.encode())
    
    s.settimeout(5)
    resposta = s.recv(1024).decode()
    
    if resposta == "handshake_ok":
        print("Handshake concluído com sucesso.\n")
        
        # Implementação do modo de envio
        if modo_envio == 1:
            print("Enviando em modo INDIVIDUAL...\n")
            for idx, pacote in enumerate(pacotes, 1):
                checksum = calcular_checksum(pacote)
                pacote_enviado = f"{checksum:03d}|{pacote}"
                s.sendall(pacote_enviado.encode())
                print(f"Pacote {idx} enviado: '{pacote_enviado}'")
                if idx < len(pacotes):
                    print("Aguardando 1 segundo para enviar o próximo pacote...")
                    sleep(1)
        else:
            print("Enviando em modo LOTE...\n")
            for idx, pacote in enumerate(pacotes, 1):
                checksum = calcular_checksum(pacote)
                pacote_enviado = f"{checksum:03d}|{pacote}"
                s.sendall(pacote_enviado.encode())
                print(f"Pacote {idx} enviado: '{pacote_enviado}'")
        
        print("\nTodos os pacotes foram enviados.")
    else:
        print(f"Resposta inesperada do servidor: {resposta}")
except Exception as e:
    print(f"Ocorreu um erro: {e}")
finally:
    s.close()
    print("Conexão fechada.")
