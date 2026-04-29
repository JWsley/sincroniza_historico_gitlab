import requests
import os
import subprocess
from datetime import datetime
from dotenv import load_dotenv

# Carrega variáveis de um arquivo .env se ele existir
load_dotenv()

# === CONFIGURAÇÕES CARREGADAS DO .ENV ===
GITLAB_URL = os.getenv("GITLAB_URL", "https://seu-gitlab-privado.com.br")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
GITHUB_REPO_PATH = os.getenv("GITHUB_REPO_PATH", "/home/jwcbf-debian/PROJETOS/CODEBASE/gitlab-sync")
SINCE_DATE = os.getenv("SINCE_DATE", "2026-01-01")
BRANCH = os.getenv("DESTINATION_BRANCH", "main")

def run_git_command(command):
    subprocess.run(command, shell=True, check=True, cwd=GITHUB_REPO_PATH)

def get_gitlab_activity():
    if not GITLAB_TOKEN:
        print("Erro: GITLAB_TOKEN não encontrado no arquivo .env")
        return {}

    activity_by_date = {}
    page = 1
    
    print(f"Buscando todas as atividades de {GITLAB_URL}...")
    
    while True:
        url = f"{GITLAB_URL}/api/v4/events"
        params = {
            "private_token": GITLAB_TOKEN,
            "after": SINCE_DATE,
            "per_page": 100,
            "page": page
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            events = response.json()
        except Exception as e:
            print(f"Erro ao acessar GitLab: {e}")
            break
        
        if not events:
            break
            
        for event in events:
            date_str = event['created_at'].split('T')[0]
            
            # Se for push, conta os commits. Se for qualquer outra atividade (issue, comment, etc), conta como 1.
            if event.get('action_name') in ['pushed to', 'pushed new']:
                commit_count = event.get('push_data', {}).get('commit_count', 1)
                # Às vezes o commit_count vem como 0 em alguns tipos de push de sistema
                commit_count = max(commit_count, 1)
            else:
                commit_count = 1
                
            activity_by_date[date_str] = activity_by_date.get(date_str, 0) + commit_count
            
        print(f"Lendo página {page}...")
        page += 1

    # Filtra apenas dias que realmente tiveram atividade > 0
    return {k: v for k, v in activity_by_date.items() if v > 0}

def sync_to_github(activity):
    if not activity:
        print("Nenhuma atividade encontrada para sincronizar.")
        return

    print(f"Sincronizando {len(activity)} dias de atividade...")
    
    for date_str in sorted(activity.keys()):
        count = activity[date_str]
        git_date = f"{date_str} 12:00:00"
        
        print(f"Dia {date_str}: criando {count} commits...")
        
        for _ in range(count):
            env_vars = f'export GIT_AUTHOR_DATE="{git_date}" && export GIT_COMMITTER_DATE="{git_date}"'
            cmd = f'{env_vars} && git commit --allow-empty -m "Sync GitLab activity" --no-gpg-sign'
            run_git_command(cmd)

    print(f"\nFazendo push para o GitHub (branch: {BRANCH})...")
    try:
        run_git_command(f"git push origin {BRANCH}")
        print("Sucesso! Verifique seu gráfico no GitHub.")
    except Exception as e:
        print(f"Erro ao fazer push: {e}")

if __name__ == "__main__":
    if not os.path.exists(GITHUB_REPO_PATH):
        print(f"Erro: Caminho {GITHUB_REPO_PATH} não encontrado.")
    elif not os.path.exists(os.path.join(GITHUB_REPO_PATH, ".git")):
        print(f"Erro: A pasta {GITHUB_REPO_PATH} não é um repositório Git.")
    else:
        data = get_gitlab_activity()
        sync_to_github(data)
