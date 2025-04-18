import socket

HOST = '127.0.0.1'
PORT = 50000

modo_operacao = 2
tamanho_max = 3

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
        tamanho_max = int(input("Digite o tamanho máximo (1 a 3): "))
        if 1 <= tamanho_max <= 3:
            break
        else:
            print("Tamanho inválido. Digite um número entre 1 e 3.")
    except ValueError:
        print("Entrada inválida. Digite apenas números.")

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    s.connect((HOST, PORT))
    print(f"Conectado ao servidor {HOST}:{PORT}")
    
    mensagem_handshake = f"modo={modo_operacao},tamanho={tamanho_max}"
    s.sendall(mensagem_handshake.encode())
    
    s.settimeout(5)
    data = s.recv(1024)
    resposta = data.decode()
    
    if resposta == "handshake_ok":
        print("Handshake concluído com sucesso.")
    else:
        print(f"Resposta inesperada do servidor: {resposta}")

except socket.timeout:
    print("O servidor demorou para responder, o tempo de espera foi excedido.")
except ConnectionRefusedError:
    print("Não foi possível se conectar ao servidor. Verifique se o servidor está em execução.")
except Exception as e:
    print(f"Ocorreu um erro: {e}")
finally:
    s.close()
    print("Conexão fechada.")
