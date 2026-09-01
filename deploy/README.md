# Nest deployment

Run these commands over SSH after reviewing the code and tests:

```bash
mkdir -p ~/apps/sponsored-provider/{current,shared}
git clone https://github.com/jeremy341/sponsored-provider.git ~/apps/sponsored-provider/current
python3 -m venv ~/apps/sponsored-provider/venv
~/apps/sponsored-provider/venv/bin/pip install -e ~/apps/sponsored-provider/current
chmod 700 ~/apps/sponsored-provider/shared
cp ~/apps/sponsored-provider/current/.env.example ~/apps/sponsored-provider/shared/.env
nano ~/apps/sponsored-provider/shared/.env
mkdir -p ~/.config/systemd/user
cp ~/apps/sponsored-provider/current/deploy/sponsored-provider.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now sponsored-provider
systemctl --user status sponsored-provider
```

Keep the service bound to localhost until TLS and access restrictions are configured. Never paste Alibaba credentials into GitHub, chat, or shell history.

