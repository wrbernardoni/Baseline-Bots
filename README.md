# Baseline Bots
 
Here are the collection of bots that I used as a baseline to test my bot while developing my bot for the first tournament for Reconnaissance  Blind Chess. Hopefully they'll be useful in developing new bots for all y'all!

A lot of these bots use the SortedList package, and the final bot I used in the first tournament, stocky_inference uses Stockfish and needs an environment variable pointed to the executable of Stockfish named STOCKFISH_ENV_VAR

# Bots
## Random Bots
These are the floor for the baseline. They act randomly, so they should not be able to beat a bot reliably, but by acting randomly they are somewhat unpredictable, so this is useful to see how your bot acts when its scans aren't giving it much information.

**randombot**: Randomly selects moves.

**retaliation**: Randomly selects moves, but if a piece is taken then it will take a move to kill whatever took one of its pieces if possible.

## Beam Search bots
These bots use a beam search for movement selection. This tends to make them pretty opportunistic and optimistic. They act like the other player is playing with their best interest in mind, and tend to be able to exploit behaviour that is beneficial to the opponent.

**4_deep**: Uses a beam search to search 4 moves deep and select the best movement. Maintains a single board possibility based off of random scans.

**4_deep_with_inference**: Same as 4_deep, except it updates its board when pieces are taken to guess which enemy piece took one of its pieces.

**8_deep**: Beam searches 8 moves forwards.

**8_deep_with_inference**: Same as 8_deep, except it updates its board when pieces are taken to guess which enemy piece took one of its pieces.

**variable_deep**: Depending on how likely the bot thinks it will win, and how much time it has, the bot adjusts how deep it searches with a beam search.

## Aggressive Bots
These bots only try to attack and take the king. They are useful to see if your scanning policy can detect certain "sneak attacks".

**aggressive_horse**: Uses breadth-first search off of a single maintained board to find the fastest series of movements using only knights to take the enemy king. If no knights remain then the bot goes to random moves.

**aggressive_tree**: Uses breadth-first search off of a single maintained board to find the fastest series of movements using any pieces to take the enemy king.

## Monte Carlo Bots
These bots tend to be a bit smarter than the other bots who just try to exploit certain features. They are a good way of seeing how your bot performs against more rounded but weaker bots.

**full_monte**: Maintins a single board and uses a monte-carlo tree search (randomly simulates games from possible boards) to determine its move. Senses where it will move next.

**full_monte_nd**: Works similarly to full_monte but with some different heuristics applied.

**defensive_scan**: Similar to full_monte, but senses based off of where it believes enemies could be which put its king in check.

**defensive_scan_path**: Like defensive_scan, but instead of scanning where it believes threats could be, it scans along paths which lead to its king, to lower the number of unknown threats.

**defensive_scan_shortest**: Like defensive_scan_path, but instead of scanning which path was not seen for the longest time, it scans based off of which path is the shortest path to the king.

**defensive_scan_pw**: Like defensive_scan, but with modified heuristics on its move search policy.

**naive_alpha**: Maintains a single board and uses a alpha-beta search and a fixed evaluation criteria to determine the best move.

**monte_alpha_2**: Uses an alpha-beta search to determine its move, with a monte-carlo method to evaluate boards (randomly plays out the board and sees how likely it is to win in this random playout)

## Bots who keep track of all possible board states

**inference**: Maintains all possible board states, scans to reduce number of possible boards, and chooses the best worst move. Tends to time out, but is a good chassis to build off of, since maintaining the board states is already done.

**stocky_inference**: Maintains 500 possible board states and acts based off of the worst possible result from any of them. Scans to reduce the number of board states. This was the bot ran in the competition.