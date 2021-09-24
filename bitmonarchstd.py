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

        peers.sort(key=lambda p: p.id)
        pieceCount = {}

        for peer in peers:
            avail_pieces = peer.available_pieces
            for piece in avail_pieces:
                if piece in pieceCount:
                    pieceCount[piece] += 1
                else:
                    pieceCount[piece] = 1

        rarestPieces = sorted(pieceCount, key=pieceCount.get)

        # index is piece ID, value is how often it shows up

        # Iterate through all peers
        #    For each peer, request the rarest pieces first
        for peer in peers:
            for piece_id in rarestPieces:
                if (piece_id in np_set) and (piece_id in peer.available_pieces):
                    start_block = self.pieces[piece_id]
                    r = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(r)

        requests = sorted(requests, key=lambda x: (pieceCount[x.piece_id], random.random()))
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
        friendliestDict = {}

        # 3 Upload Slots Normally
        chosen = []
        bws = []

        request_id = list(set([r.requester_id for r in requests]))

        if round > 0:
            if round >= 2:
                i = -2
            else:
                i = -1
            for downloadlist in history.downloads[i:]:
                for download in downloadlist:
                    if download.from_id in request_id:
                        if download.from_id in friendliestDict:
                            friendliestDict[download.from_id] = friendliestDict[download.from_id] + download.blocks
                        else:
                            friendliestDict[download.from_id] = download.blocks

            # Now sort friendlistSet by blocks allowed you to download
            friendliestDict = dict(sorted(friendliestDict.items(), key=lambda item: item[1]))
            friendliestIDs = list(friendliestDict.keys())
        else:
            friendliestIDs = list(request_id)
            random.shuffle(friendliestIDs)
        
        length = min(3, len(friendliestIDs))
        # add randos to end of this in our request set
        chosen = friendliestIDs[:length]
        chosen += random.sample(request_id, min(4 - length, len(request_id)))

        bws = even_split(self.up_bw, max(1,len(chosen)))

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw) for (peer_id, bw) in zip(chosen, bws)]
        
        return uploads
