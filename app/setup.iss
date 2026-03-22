; Script Inno Setup - Sistema Hotel Santos
; Coloque este arquivo em: app/setup.iss

#define AppName "Sistema Hotel Santos"
#define AppVersion "1.0.0"
#define AppPublisher "Hotel Santos"
#define AppExeName "SistemaHotelSantos.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/gabriel-mendesr/DEVELOP
AppSupportURL=https://github.com/gabriel-mendesr/DEVELOP/issues
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Saída do instalador
OutputDir=installer_output
OutputBaseFilename=SistemaHotelSantos-Setup-Windows
; Compressão máxima
Compression=lzma2/ultra64
SolidCompression=yes
; Visual moderno
WizardStyle=modern
; Requer privilégio de admin para instalar em Program Files
PrivilegesRequired=admin
UsedUserAreasWarning=no
; Ícone do instalador (opcional - descomente se tiver um .ico)
; SetupIconFile=assets\icon.ico
; Imagem lateral do wizard (opcional)
; WizardImageFile=assets\wizard_banner.bmp
; Versão mínima Windows 10
MinVersion=10.0

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; \
  Description: "Criar atalho na Área de Trabalho"; \
  GroupDescription: "Atalhos adicionais:"
Name: "startupicon"; \
  Description: "Iniciar automaticamente com o Windows"; \
  GroupDescription: "Atalhos adicionais:"; \
  Flags: unchecked

[Files]
; Copia todos os arquivos gerados pelo PyInstaller (--onedir)
Source: "dist\SistemaHotelSantos\*"; \
  DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Menu Iniciar
Name: "{group}\{#AppName}"; \
  Filename: "{app}\{#AppExeName}"
Name: "{group}\Desinstalar {#AppName}"; \
  Filename: "{uninstallexe}"
; Área de Trabalho (opcional, tarefa acima)
Name: "{commondesktop}\{#AppName}"; \
  Filename: "{app}\{#AppExeName}"; \
  Tasks: desktopicon
; Inicialização automática (opcional, tarefa acima)
Name: "{commonstartup}\{#AppName}"; \
  Filename: "{app}\{#AppExeName}"; \
  Tasks: startupicon

[Run]
; Oferecer para abrir o app ao finalizar instalação
Filename: "{app}\{#AppExeName}"; \
  Description: "Iniciar {#AppName} agora"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Limpa arquivos criados pelo app durante uso
Type: filesandordirs; Name: "{commonappdata}\hotel_santos_logs"
Type: files; Name: "{commonappdata}\.shs_version"
