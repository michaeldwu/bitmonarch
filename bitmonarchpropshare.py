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


class BitMonarchPropShare(Peer):
    def post_init(self):
        print(("post_init(): %s here!" % self.id))
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"

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
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        generousPeers = {}
        request_ids = {request.requester_id for request in requests}

        chosen = []
        bws = []

        # In round 0, there are two ways to approach the optimistic unchoking 10%
        # 1) One peer gets 10% exactly, the rest of the peers split the 90%
        # 2) All peers split the 90% equally, one peer gets the extra 10%
        # We opted to go for option 2, as that better represents the spirit of optimistic unchoking

        if not history.downloads:
            if len(request_ids) != 0:
                chosen = request_ids
                bws = even_split(int(self.up_bw * 0.9), len(request_ids))
                bws[random.randint(0, len(bws))] += 0.1 * self.up_bw
        else:
            for download in history.downloads[-1]:
                if download.from_id in generousPeers:
                    generousPeers[download.from_id] = generousPeers[download.from_id] + download.blocks
                else:
                    generousPeers[download.from_id] = download.blocks

            inter = set()
            not_inter = set()

            for request_id in request_ids:
                if request_id in generousPeers:
                    inter.add(request_id)

            not_inter = request_ids - inter

            total_downloaded = 0
            for id in inter:
                total_downloaded += generousPeers[id]

            for id in inter:
                chosen.append(id)
                bws.append(generousPeers[id] / total_downloaded * (0.9 * self.up_bw))

            # If not_inter is empty (all requesters were generous)
            # Then we will give one of the requesters the extra 10%
            if not not_inter:
                bws

            # if not_inter:
            #     chosen.append(random.choice(list(not_inter)))
            #     bws.append(0.1 * self.up_bw)
            # elif :
            #     bws[random.randint(0, len(bws) - 1)] += 0.1 * self.up_bw


        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]

        return uploads
