#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

"""


We need to implement three things:
1. Rarest-first
2. Reciprocation
3. Optimistic unchoking

Step 1: Rarest First
Whenever a peer downloads a piece of the file, it sends per-piece
have messages to the peers in its neighborhood. Each peer maintains 
an estimate of the availibility of each piece by counting how many of 
its neighbors have the pieces.

While leeching, a peer i is continually trying to download from its 
neighbors.

Step 2: Reciprocation
The decision made by the reference client about which peers to unchoke is
based on the recent download rate from other peers. Given S unchoke slots,
the reference client makes a new decision every time period, unchoking S-1
peers from which it received the highest average download rate during the
last 2 time periods. (which agents have allowed you to download from them)

   * Sort who's friendliest first to you (highest number of blocks in AgentHistory)
   * Check what pieces they need
   * If you have the piece they need, put them in your Upload slot

   Use AgentHistory to be able to see the highest average download rate

Step 3: Optimistic unchoking
Every 3 time periods, the reference client allocates an additional optimistic
unchoking slot, to a random peer from its neighborhood. The reference client
splits its upload bandwith equally among the S slots.

Optimistic unchoking helps a client to explore its neighborhood and find peers
that will reciprocate and provide high upload bandwidth.
"""


class BitMonarchStd(Peer):
    def post_init(self):
        print(("post_init(): %s here!" % self.id))
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
        self.optimisticUnchoked = 0
    
    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = list(filter(needed, list(range(len(self.pieces)))))
        np_set = set(needed_pieces)  # sets support fast intersection ops.


        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)
        
        # Whenever a peer downloads a piece of the file, it sends per-piece have messages to the peers in its neighborhood. Each peer maintains 
        # an estimate of the availibility of each piece by counting how many of its neighbors have the pieces.

        # NEED TO SORT BY RAREST FIRST RIGHT? Is this the place??
        peers.sort(key=lambda p: p.id)
        # print(peers)

        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.

            # iterate through sorted rarityList, check if key is in intersection
            # 

            # Should also be rarest first
            for piece_id in random.sample(isect, n):
                # aha! The peer has this piece! Request it.
                # which part of the piece do we need next?
                # (must get the next-needed blocks in order)
                start_block = self.pieces[piece_id]
                r = Request(self.id, peer.id, piece_id, start_block)
                requests.append(r)

        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers. Will contain available histories and 
        history -- history for all previous rounds

        example history:
        AgentHistory(downloads=[[Download(from_id=Seed0, to_id=BitMonarchStd2, piece=0, blocks=1)], [Download(from_id=Seed0, to_id=BitMonarchStd2, piece=1, blocks=1)]], uploads=[[], []])

        returns: list of Upload objects.

        In each round, this will be called after requests().


            * Sort who's friendliest first to you (highest number of blocks in AgentHistory)
            * Check what pieces they need
            * If you have the piece they need, put them in your Upload slot
        """

        round = history.current_round()

        # Find everyone who's allowed you to download from them before and add you to this set
        friendliestSet = {}
        
        # 3 Upload Slots Normally
        chosen = []
        bws = []

        if len(history.downloads) > 0:
            if len(history.downloads) >= 2:
                i = -2
            else:
                i = -1
            for download in history.downloads[i]:
                if download.from_id in friendliestSet:
                    friendliestSet[download.from_id] = friendliestSet[download.from_id] + download.blocks
                else:
                    friendliestSet[download.from_id] = download.blocks

            # Now sort friendlistSet by blocks allowed you to download
            dict(sorted(friendliestSet.items(), key=lambda item: item[1]))

            if len(friendliestSet.keys()) != 0:
                chosen = list(friendliestSet.keys())[0:3]
                bws = even_split(self.up_bw, len(chosen))
                # if round % 3 == 0:
                #     if requests is not None:
                #         print("AI YA")
                #         self.optimisticUnchoked = random.choice(requests)
                # chosen.append(self.optimisticUnchoked)
        else:
            #random from requests
            if requests:
                requestsApproved = random.sample(requests, 3)
                chosen = [requestsApproved[0].requester_id, requestsApproved[1].requester_id, requestsApproved[2].requester_id]
                bws = even_split(self.up_bw, len(chosen))

        

        

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
