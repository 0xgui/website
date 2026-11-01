# Builds

Things I’m making with my hands, and a few small tools I’ve made for myself and put on GitHub.

## Robots

### [SO-101 robotic arm](https://silvags.com/robots/so-101/)

**In progress** · robotics, imitation learning

Two 6-DOF arms built from scratch: 3D-printed from open-source designs, twelve STS3215 servos, leader-follower teleop. The first time I grabbed the leader and watched the follower mirror me in real time, that was the trigger. Now I’m teaching it to do things on its own.

1. Build & assemble
2. Teleop moving

3. Imitation learning *now*
4. Sim-to-real + VLA

### [Pico](https://silvags.com/robots/pico/)

**Self-righting works** · robotics, reinforcement learning

Two servos, a tiny ESP32 board, and one job: get back up. A policy trained in MuJoCo moves the arms when the robot falls. My build now recovers reliably on real hardware. Next comes measuring those recoveries and trying new ideas.

1. Build & assemble
2. Calibrate

3. Self-righting
4. Experiments *next*

I also tinker with smaller ESP32 gadgets. When one is worth writing up, it’ll show up here.

## Open source

- [agent-pr-gate](https://github.com/0xgui/agent-pr-gate) — a GitHub Action that gates agent-authored pull requests on risk tier, evidence, and review rounds.

- [write](https://github.com/0xgui/write) — a minimal GTK writing app, for the simple pleasure of putting words on a page.

More on [GitHub](https://github.com/0xgui).
