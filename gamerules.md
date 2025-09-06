

GOON SQUAD GALAXY – GAME SIMULATOR RULES

1. Game Overview
In Cosmic Horror in Goon Squad Galaxy, each player commands a squad of GOONs—grotesque monsters, alien machines, and freakish leaders—battling for survival across a ruined cosmos.
 As your goons use abilities and help deploy new goons they accumulate Wind which represents fatigue, exposure to cosmic forces, or the strain of action.
 When a GOON reaches 4 Wind it is destroyed and sent to the dead pool. Dead pool is a communal discard pile shared among all players. Wind is everything: your cost, your limit, your death.
At the start of your turn, each GOON card unwinds to remove 1 Wind.
2. Quickstart Guide
- Each player uses a deck with at least 60 cards
- Your deck includes a Squad Leader, Squad GOONs, and Basic GOONs and a Titan
- You lose if your deck runs out or your Squad Leader is destroyed.
- Squad Leader begins in play. Other GOONs must be deployed. 
3. Turn Structure
1. Draw Phase
- First turn draw 6 cards
- all subsequent turns Draw 1 card from your deck.
 
2. Unwind Phase
- Rotate each GOON 90° clockwise to remove 1 of accumulated Wind 
 
 (phases 3 and 4 are interchangeable)
3. Action Phase
- YOu may Use any GOON abilities the GOON is able to  pay Wind for.
- Abilities may apply Wind to the GOON they belong to. (They may also require mechanical or biological resources from the dead pool to use)
 
4. Deploy Phase
- Deploy new GOONs from hand by spending Wind.(They may also require mechanical or biological resources from the dead pool to deploy)
- GOONs enter play at 0 Wind.
- any goons in play can contribute wind for deploying new goons as long as they werent deployed in the current turn
- freshly deployed goons cannot act until the turn after they are deployed. That means they cant use abilities(Passive abilities are always in effect and are an exception ) and may not contribute wind to deploy new GOONs
 
5. End Phase
- Resolve any end-of-turn effects.



-------
OBJECTIVE
Destroy opposing team's GOONs by targeting them with GOON abilities that wind them up. One field is clear of their GOONs,  destroy their Squad Leader to win.

STRATEGY
Target enemy GOONs with multiple GOONs' abilities in a turn to increase enemy wind to 4 which destroys them. Focus on destroying enemy GOONs.

WIND SYSTEM


All units (GOONs) are destroyed at 4.


Units gain Wind () when paying to deploy other GOONs or activating abilities.


Wind counts are tracked per GOON.


Wind unwinds at the start of each turn:  →  →  etc.


-------



UNIT TYPES


SL = Squad Leader (1 per deck, always starts in play)


SG = Squad GOON (limit 1 in play at a time)


BG = Basic GOON (unlimited)


Titans = Special units with steep costs, untargetable, immune


-------



DEPLOYMENT RULES

GOONs cost Wind and sometimes mechanical or biological resources to deploy

Any GOON (SL, SG, BG but NOT Titants) that has been in play for a full turn can pay Wind to contribute to paying the deploy wind cost for another GOON. 

GOONs enter play with 0 wind

GOONs cannot use abilities or contribute wind to deploy other GOONs on the round they are deployed


-------



WIND SPENDING


Units with 1–3 may spend Wind to take actions.


A unit destroyed by reaching 4 still completes its action.


Units may never exceed 4.



-------


PROTECTION RULES
To win the game you must destroy the opposing players' squad leader. When Squad or Basic GOONs are in play the Squad Leader may not be the target of enemy abilities. They "protect” the SL
If any Basic GOON (BG) is in play, Squad Leaders (SLs) cannot be attacked.


If any Squad GOON (SG) is in play, Squad Leaders (SLs) cannot be attacked.


Titans dont protect Squad Leaders (SLs)

-------

SPECIAL GOON PROPERTIES

Resist- A GOON may have Resist which will subtract 1 wind from the total wind applied to them from a hostile ability
Doesnt Unwind - Goon does not unwind regularly during the unwind phase. 


-------



ABILITIES

GOON Abilities are used to help fiendly GOONs and attack, destory and hinder enemy GOONs
GOONs may have multiple abilities, but may only use one per turn as long as they are able to pay for it.
GOON ability wind cost is paid for by the GOON itself and no other (unless an ability changes this rule)
Some abilities cost Mechanical or Biolocical resources form the dead pool to use
Some abilites cost nothing to use but still count as the single ability use allowed in a turn
Some abilities are passive and are in effect from the time the GOON is deployed. These abilites do not require payment. 



-------



HAND & DRAW RULES


Players draw 1 card at the start of their turn.


Players lose if they cannot draw a card.


-------



CARD LIMITS


Each deck has a minimum of 60 cards.


Max 4 copies of any card (except Titans = 1).


A given type of SG is limited to 1 in play per player. Vex and Krax are SGs. You may have Vex and Krax in play at the same time but not 2 Vex’s


-------



TITANS


Cannot be damaged, targeted
Obey the same wind rules as all other GOONs. If they spend up to 4 wind they are destroyed.


Do not protect the squad leader from being targeted by hostile abilities


-------


DEATH & DISCARD

A GOON may accumulate up to 4 wind. The 4th will destroy it. Twisting your own GOON into the 4th wind is a legal move. Whatever the GOON spent the wind on will resolve before the GOON is destroyed. 

GOONs that accumulate 4 or more wind are removed from play and go to the communal discard pile called the Dead Pool. The Dead Pool is a combination of all players dead goons.
Once in the dead pool the goons become a resource for special deploys and abilities. Some deploys or abilities may require Biological or Mechanical dead goons from the dead pool.

When a Dead Goon is used as a mechanical or biological resource they are Burned (removed from the game permanently).



INTERFACE
1)Display Goon name in board like this:
[name][rank icon SL⭐|SG🔶|BG(no icon)|TΩ ][resist icon✋][no unwind icon🚫][biological icon🥩|mechanical icon⚙️][faction icon NARC🚨|PCU🌀[deployed this turn and cannot act🔒]
example: Lokar Simmons⭐✋🥩🚨

2)Display Goon name in hand like this:
[name][rank icon SL⭐|SG🔶|BG(no icon)|TΩ ][resist icon✋][no unwind icon🚫][biological icon🥩|mechanical icon⚙️][faction icon NARC🚨|PCU🌀
example: Lokar Simmons⭐✋🥩🚨

3)Display Goon cost in hand like this:
N⟲ N⛭ N⚈
example:1⟲ 0⛭ 0⚈

4)Display Abilities in ability column in board like this:
[index][name][cost N⟲ N⛭ N⚈][text]
[index][name][cost N⟲ N⛭ N⚈][text]
...
(each ability should occupy its own line)

5)The player whos turn it is, their board should be rendered second so it is on the bottom and close to where their hand will be rendered. The player who went last turn's board should be printed first so it is on top in the console. 

6) Display the dead pool on its own line after the player boards. Display the contents of the dead pool like this
Dead Pool 🥩:N ⚙️:N

COMMANDS
1)Deploying Goons
Manually deploy a goon from hand
d[index in hand] [index of goon paying wind] [index of goon paying wind] ...
example: d0 0 1 1  <----deploy goon 0 from hand. goon 0 on board contributes 1 wind and goon 1 on board contributes 2 wind.
example:d1 0 0 <----deploy goon 1 from hand. goon 0 on board contributes 2 wind

-if part of the goon deploy cost includes biological or mechanical from the Dead Pool, automatically burn(remove from game) the appropriate type of card from the dead pool. If bio or mech is required and not present in the dead pool, deploy fails

2)Use goon ability command.

Target opponent players goon with current players goon ability. Player is using one of their goons abilities on an opponents goon. Likely some sort of attack or negative effect.
u[currrent player goon index] [ability index]>[target enemy goon index]

Target with current players goon with current players goon ability. When a player wants to target his own goon with one of his goons abilities.
u[currrent player goon index] [ability index]<[target current players goon index]

Payment notes:
When a goon uses its own ability, automatically add the wind cost of the ability to the goon. If bio or mech is part of the use cost, automatically subtract the correct type from the dead pool. if wind, mech or bio is not available to pay the use cost, the ability use fails. If the goon reaches 4 wind by paying for an ability, it is destroyed after the ability effect resolves. The maximum wind that may be appied to a goon is 4. If an ability costs 2 wind and the goon has 3 wind applied to it, it may not use the ability as it would result in a 5 wind total which is never allowed. goons may never have 5 or more wind on them.








