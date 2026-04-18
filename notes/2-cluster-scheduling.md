# dominant resource fairness
- prev DRF, max min fairness the popular allocation policy. giving each user an equal share of resources. generalized to multi resource by giving each user an equal share proportional to some resources weight

properties of min max fairness
- sharing incentive: no user is better off in a system w static partitioning
- strategy proofness: (described below)
- pareto efficient: ?
- envy free: no user prefers the allocation of another user

`strategy proofness` - term from mechanism design. a game in which each player has a weakly dominant strategy such that no player can gain by spying over other players to know what they are going to play.

> Note to self: look into mechanism design

before: 
- quincy and hadoop static partitioning, bad because a slot is often a poor match for the task demands

> vis note: plotting the cdf of how many tasks are allocated the right resources. was a little confused by the the line continuing to the right. But this just indicates that the rest of the resources are properly allocated.
> [plot](https://drive.google.com/file/d/1CVZOJMGvg_vRgNr38S7JtiypeGCUsZNN/view?usp=sharing)

> note: this notion of "cloud" operators, people whose entire job it is to manage data centers


# Autopilot

> "serving" jobs are jobs which should be served accoridng to SLOs. "batch" jobs don't have strict execution deadlines.

> compute some histogram for the last 5 minutes. bins correspond to resources, e.g. [0-100 cores][100-200 cores], etc. The value of each bin are measurements from specific seconds over the last 5 minutes.
- three algorithms
  - one is a max value over the last 5 minutes. used for jobs w minimal oom tolerance.
  - the other is a weighted average, exponentially weighted. for batch jobs which can tolerate CPU throttling.
  - a third one which weights histogram buckets by the load as well. e.g. for each job, how long does it run for?

> corr from claude: 
- hist computed every 5, but an algo might look at windows from days, weeks, etc. ago
- load is not job duration, it is how many resources a job is using at a certain point.
- weighing happens at the per sample level