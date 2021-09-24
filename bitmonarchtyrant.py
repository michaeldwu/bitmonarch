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

class BitMonarchTyrant(Peer):
    def post_init(self):
        print(("post_init(): %s here!" % self.id))
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
        self.uploadHistory = []

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

        requests = []  # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)

        # Whenever a peer downloads a piece of the file, it sends per-piece have messages to the peers in its neighborhood. Each peer maintains
        # an estimate of the availibility of each piece by counting how many of its neighbors have the pieces.

        # NEED TO SORT BY RAREST FIRST RIGHT? Is this the place??
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

        # Iterate through all peers
        #    For each peer, request the rarest pieces first
        for peer in peers:
            for piece_id in rarestPieces:
                if piece_id in np_set and piece_id in peer.available_pieces:
                    start_block = self.pieces[piece_id]
                    r = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(r)

        # Now that we have overall request list
        # Create new request list that orders requests by rarity
        request_c = requests.copy()
        sortedRequests = []
        for piece_id in rarestPieces:
            sortedwithinPiece = []
            for request in request_c:
                if piece_id == request.piece_id:
                    sortedwithinPiece.append(request)
                    request = None
            random.shuffle(sortedwithinPiece)
            sortedRequests.extend(sortedwithinPiece)

        return sortedRequests

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

        if round > 0:
            if round >= 2:
                i = -2
            else:
                i = -1
            for downloadlist in history.downloads[i:]:
                # Double counting
                for download in downloadlist:
                    if download.from_id in friendliestSet:
                        friendliestSet[download.from_id] = friendliestSet[download.from_id] + download.blocks
                    else:
                        friendliestSet[download.from_id] = download.blocks

            # Now sort friendlistSet by blocks allowed you to download
            dict(sorted(friendliestSet.items(), key=lambda item: item[1]))
            # print(friendliestSet)

            if len(friendliestSet.keys()) != 0:
                chosen = list(friendliestSet.keys())[0:3]
                if requests is not None and len(requests) != 0:
                    request_id = list(set([r.requester_id for r in requests]))
                    for i in chosen:
                        if i in request_id:
                            request_id.remove(i)

                    # Optimistic Unchoking
                    if round % 3 == 0:
                        if len(request_id) != 0:
                            self.optimisticUnchoked = random.choice(request_id)
                try:
                    chosen.append(self.optimisticUnchoked)
                except:
                    chosen.append(list(friendliestSet.keys())[4])
                bws = even_split(self.up_bw, len(chosen))
        else:
            # random from requests
            if requests:
                requestsApproved = random.sample(requests, 4)
                chosen = [requestsApproved[0].requester_id, requestsApproved[1].requester_id,
                          requestsApproved[2].requester_id]
                bws = even_split(self.up_bw, len(chosen))

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]

        return uploads
