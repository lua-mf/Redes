import socket
from datetime import datetime

def calcular_checksum(pacote):
    return sum(ord(char) for char in pacote) % 256

HOST = 'localhost'
PORT = 50000

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen()
print(f"Servidor esperando conexão do cliente em {HOST}:{PORT}...")
conn, ender = s.accept()
print('Conectado em ', ender)

handshake = conn.recv(1024).decode()
print(f"Handshake recebido: {handshake}")

try:
    partes = handshake.split(',')
    modo_operacao = int(partes[0].split('=')[1])
    tamanho_max = int(partes[1].split('=')[1])
    modo_envio = int(partes[2].split('=')[1])
    qtd_pacotes = int(partes[3].split('=')[1])
    
    print(f"Modo de operação: {modo_operacao}, Tamanho máximo: {tamanho_max}, Modo de envio: {modo_envio}, Quantidade de pacotes: {qtd_pacotes}")
    
    conn.sendall("handshake_ok".encode())
    print("\nAguardando pacotes...\n")
    
    buffer_completo = ""
    pacotes_processados = 0
    mensagem_completa = ""
    
    while pacotes_processados < qtd_pacotes:
        dados = conn.recv(1024).decode()
        
        if not dados:
            break
            
        buffer_completo += dados
        
        while buffer_completo and pacotes_processados < qtd_pacotes:
            if len(buffer_completo) < 4:
                break  # espera pelo menos 4 caracteres: 3 checksum + 1 separador
            
            checksum_recebido = int(buffer_completo[:3])
            if buffer_completo[3] != '|':
                raise ValueError("Formato inválido de pacote recebido.")
            
            conteudo_pacote = buffer_completo[4:4+tamanho_max]
            
            if len(conteudo_pacote) < min(tamanho_max, 1) and len(buffer_completo) < (4 + tamanho_max):
                break  # aguarda mais dados
            
            buffer_completo = buffer_completo[4+tamanho_max:]
            
            checksum_calculado = calcular_checksum(conteudo_pacote)
            
            horario = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            pacotes_processados += 1
            
            print(f"Pacote {pacotes_processados} recebido:")
            print(f"- Conteúdo: '{conteudo_pacote}'")
            print(f"- Tamanho: {len(conteudo_pacote)}")
            print(f"- Horário: {horario}")
            print(f"- Checksum recebido: {checksum_recebido}")
            print(f"- Checksum calculado: {checksum_calculado}")
            if checksum_recebido == checksum_calculado:
                print("- Status: Checksum OK!")
                mensagem_completa += conteudo_pacote
            else:
                print("- Status: ERRO de Checksum (pacote corrompido!)")
            print("---------------------------")
    
    print(f"\nMensagem completa reconstruída: '{mensagem_completa}'")
    
except Exception as e:
    print(f"Erro ao processar: {e}")
finally:
    conn.close()
    print("Conexão encerrada com o cliente.")