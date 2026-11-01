# I built a tiny robot that refuses to stay down

September 28, 2026 · Originally published on [Binary Paths](https://binarypaths.substack.com/p/i-built-a-tiny-robot-that-refuses)

Have you ever seen something cool that looked simple on the internet and told yourself “I should try this” and then spent the rest of the time evaluating your life’s decisions?

I had one of those.

The “something cool”: a tiny robot that stands up. I knock it over, I let go, and it tries to get up by itself. Every time. I think that is cool.

I also like learning more about robotics and a robot on the desk is a better way to do that than another tab of your web browser.

![](https://silvags.com/writing/i-built-a-tiny-robot-that-refuses/images/01.webp)

*Pico.*

## The plan

It all started when I saw a maker called *HomeMadeGarbage* who built this tiny robot that would always get up. Always! I thought it was so cool and interesting that I had to make my own.

So, like the naive engineer that I am, I tried to build it and add my improvements on top of it.

Pico is small. Two servomotors, 3D printed parts, a little drone battery, and a development board about the size of a small candy.

You tell the robot “go to this angle” and it will try. The board has the same kind of sensor that knows you flipped your phone. A small program looks at the tilt and moves the arms.

People who already work in robotics call that program a policy.

The source code for it and more is [here on my github](https://github.com/0xgui/pico-self-rising-robot).

The plan:

Print the foot. Print the arms. Screw the motors on. Plug the wires in. Flash the firmware.

In my head, that was the plan.

Video

[Media](https://silvags.com/writing/i-built-a-tiny-robot-that-refuses/images/02.webm)

*First parts being printed.*

## The plan is never straightforward

**First problem, assembly.**

If you knew how many times I had to reprint the part below, just because I messed it up with the wrong type of screws, or because it would not fit the servo motor correctly, or because I damaged it somehow…

I don’t want to talk about it. Let’s just say I don’t have black filament anymore and I had to print it in red.

![](https://silvags.com/writing/i-built-a-tiny-robot-that-refuses/images/03.webp)

*Still have nightmares about it.*

**Second problem, the wires.**

When testing the robot, some wires got loose because of the movement and the general jankiness of it. Since it was the first prototype, I thought that for testing, duct tape and a bit of soldering was enough.

I guess it was not.

I stopped being a caveman and set the cables in a sturdier way.

![](https://silvags.com/writing/i-built-a-tiny-robot-that-refuses/images/04.webp)

*Wires just got loose after some tests.*

**Third problem, the arms were connected wrong.**

Each motor has a signal wire, and that wire has to land on the right pin. The motor also has to turn the direction the program expects. Mine didn’t. Wrong pins. Wrong direction. A command that meant “move up” went down, and the robot threw itself at the table like it meant to.

The code was fine. My wiring was not.

So I sent one command, watched which arm moved, wrote it down, and sent another, until the arms agreed with the version on the code.

Thank god we have AI nowadays to help troubleshoot these things.

**Fourth problem, the robot thought up was down.**

Video

[Media](https://silvags.com/writing/i-built-a-tiny-robot-that-refuses/images/05.webm)

*That little grey cube’s position was the issue.*

Pico sitting flat on the desk, perfectly still, and the program was certain it was upside down. Every get-up attempt started from a lie.

The tilt math. My board, the little grey cube (the brain of all of this) is mounted in a different orientation than the original build, and the formula was 180 degrees off.

It should be faced up and not down as I mounted it.

But hey, at least it was moving! Progress!

Patched the code and off it went.

**Fifth problem, the USB port said no.**

Video

[Media](https://silvags.com/writing/i-built-a-tiny-robot-that-refuses/images/06.webm)

*USB Ports didn’t have enough power to handle the motors load.*

With both motors moving at the same time plus the development board draining energy, my USB ports just did not have enough juice to handle all the load when the load hit its peak.

Solution?
Why won’t you just connect the battery and try it?

It worked.
(Thanks AI gods again)

**No more problems.**

Five problems. Reprints. Loose wires. Wrong pins. Tilt upside down. Power collapse.

Two of them were just building the thing. The other three looked like code bugs. None of them were the code.

It never changed. I changed everything around it without realizing and because of that I needed to adapt the code to the way I built it.

Hardware is hard!

## It works. Rise!

Video

[Media](https://silvags.com/writing/i-built-a-tiny-robot-that-refuses/images/07.webm)

*Happy little guy.*

Below is a video so you can hear the motors and see how it behaves:

I knocked it over and over again.

The arms moved. The body moved.

It stood up, and stayed up.

Every time.

I knocked it over maybe fifty times, and about five of those it stayed down, unable to get up. I think that’s pretty good!

I can finally say it: **I added a new robot to my collection.
**

## Where the “get up” comes from

Nobody wrote “swing this arm, then that one” by hand for every situation or environment.

The program learned the motion in a simulator, before it ever touched the robot.

The simulator, MuJoCo, think a physics engine for robots, drops a virtual Pico on its side, over and over. Every attempt gets a score: points for being more upright, penalties for staying tilted, for wiggling once it’s already up, for the wrong body height.

Video

[Media](https://silvags.com/writing/i-built-a-tiny-robot-that-refuses/images/08.webm)

*Pico in simulation*

A training method called PPO (Proximal Policy Optimization) nudges the program toward better scores.

Try, score, adjust. Thousands of times.

It didn’t start from zero. The original author scripted a get up by hand and made the robot train on it.

Also, pretty nice to have AI and simulations to help us before we spend money on real hardware.

---

Is the robot useful now? Probably not.

Was it a pain to build? For sure.
Was it fun? For sure.

Maybe next I try to make it jump.

*GS*
