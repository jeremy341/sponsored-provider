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

The service listens on port 8090 for the Nest domain proxy. Keep the dashboard protected by `ADMIN_TOKEN`; never paste Alibaba credentials into GitHub, chat, or shell history. This deployment is intentionally separate from any existing app on port 8080.
