# SO-101 robotic arm

Build log · Day 01 · March 5, 2026

A 6-DOF robotic arm, built from scratch with twelve STS3215 servos, two 3D-printed arms, leader-follower teleop, and a slowly growing brain.

**Status:** In progress, step 3 of 4

**Progress:** ✓ Build & assemble
✓ Teleop moving
→ **Imitation learning** (now)
· Sim-to-real + VLA

**Hardware:** STS3215 × 12, 3D-printed (PLA/PETG)

**Stack:** Python, ROS2, LeRobot

**Links:** [GitHub](https://github.com/0xgui/SO-101) · [Origin story](https://binarypaths.substack.com/p/physical-ai-is-here-and-im-building)

3D model of the SO-101 robotic arm. Drag to rotate.

![](https://silvags.com/robots/so-101/arms-wide.webp)

*The real SO-101 CAD model. Drag to rotate, scroll to zoom.*

## Day 01 · The arms, they move

![Both SO-101 arms assembled on the desk](https://silvags.com/robots/so-101/arms-wide.webp)

*Two arms, a lot of servos, built from scratch.*

I 3D-printed it part by part with a Bambu printer I bought, ordered twelve STS3215 servos from AliExpress at €20 each, and followed open-source designs and instructions. Two arms, built completely from scratch. The 3D printing alone took about two days for both.

Did I assemble everything on the first try? Ahah, no. At one point I had fully configured the leader arm… as a follower. Wrong configuration, wrong setup. I realized it only after everything was done, and had to redo it all from scratch.

It’s also been a great opportunity to put my mechanical and electrical skills to the test, drawing on my background as an automotive engineer. There’s just something special about seeing something move. Atoms moving.

3D printing the arms

[Media](https://silvags.com/robots/so-101/teleop-v1.webm)

*3D printing the arms.*

> The moment I grabbed the leader arm, moved it slowly and watched the follower mirror every single action in real time. That was it. The trigger. Something about seeing a machine you built with your own hands actually move hits differently than anything in software.

It’s physical. It’s immediate. It’s hard. It’s real. Now I just need to give it a brain.

Teleoperation: the follower arm mirrors the leader

[Media](https://silvags.com/robots/so-101/teleop-v2.webm)

*Teleop run.*

Right now it’s pure teleoperation: I move one arm, the other follows. No AI, no learning, just direct position mapping. That moment alone was enough to pull me completely into this new world of hardware.

## What’s next

- Teach the arms tasks by demonstration: move them through a motion a few dozen times and let them learn to replicate it (imitation learning). This is the current step.

- Sim-to-real with [NVIDIA Isaac Sim](https://developer.nvidia.com/isaac/sim) and [Gazebo](https://gazebosim.org/).

- Finally, a vision-language-action model so it can see, reason, and act.

More on the why and the bigger picture in the [origin story on Binary Paths](https://binarypaths.substack.com/p/physical-ai-is-here-and-im-building). Calibration scripts and more on [GitHub](https://github.com/0xgui/SO-101).

*Next entry: imitation learning, first demonstrations.* [All builds](https://silvags.com/builds/)
