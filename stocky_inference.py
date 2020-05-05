import random
from reconchess import *
from sortedcontainers import SortedList
from multiprocessing import Pool, TimeoutError
import os
import chess.engine
import datetime

STOCKFISH_ENV_VAR = 'STOCKFISH_EXECUTABLE'

def partition (list_in, n):
	random.shuffle(list_in)
	return [list_in[i::n] for i in range(n)]

class StockyInference(Player):
	def __init__(self):
		self.color = None
		self.moveNum = 0
		self.approxTime = 900
		self.potBoards = {}
		self.score = 0
		self.opponent_move_results = []
		self.sense_results = []
		self.my_move_results = []
		self.checkpoints = SortedList(key=lambda x: x[0])
		self.won = False
		self.initialBoard = None
		self.mvRecovery = 0
		self.enemy = ""

		# make sure stockfish environment variable exists
		if STOCKFISH_ENV_VAR not in os.environ:
			raise KeyError(
				'TroutBot requires an environment variable called "{}" pointing to the Stockfish executable'.format(
					STOCKFISH_ENV_VAR))

		# make sure there is actually a file
		self.stockfish_path = os.environ[STOCKFISH_ENV_VAR]
		if not os.path.exists(self.stockfish_path):
			raise ValueError('No stockfish executable found at "{}"'.format(self.stockfish_path))

		# initialize the stockfish engine
		self.engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)

	def advanceBoardsNoTake(self, brds):
		newBoards = {}
		for k in brds:
			tBoard = chess.Board(k)
			if tBoard.turn == self.color:
				tBoard.turn = (not self.color)
				#print("null1")

			if tBoard.has_kingside_castling_rights(not self.color):
				king = tBoard.king(not self.color)
				targ = chess.square(chess.square_file(king) + 2, chess.square_rank(king))
				mv = chess.Move(king, targ)
				ttBoard = tBoard.copy()
				ttBoard.push(mv)
				newBoards[ttBoard.fen()] = ttBoard.copy()
			if tBoard.has_queenside_castling_rights(not self.color):
				king = tBoard.king(not self.color)
				targ = chess.square(chess.square_file(king) - 2, chess.square_rank(king))
				mv = chess.Move(king, targ)
				ttBoard = tBoard.copy()
				ttBoard.push(mv)
				newBoards[ttBoard.fen()] = ttBoard.copy()

			for mv in tBoard.pseudo_legal_moves:
				#if tBoard.is_castling(mv):
				#	continue

				if tBoard.piece_at(mv.to_square) is None:
					ttBoard = tBoard.copy()
					ttBoard.push(mv)
					#if ttBoard.status() == chess.STATUS_VALID or ttBoard.status() == chess.STATUS_OPPOSITE_CHECK:
					newBoards[ttBoard.fen()] = ttBoard.copy()
			newBoards[k] = tBoard
		return newBoards

	def advanceBoardsTaken(self, tile, brds):
		newBoards = {}
		for k in brds:
			tBoard = chess.Board(k)
			if tBoard.turn == self.color:
				tBoard.turn = (not self.color)
				#print("null2")
			for mv in tBoard.pseudo_legal_moves:
				if (tBoard.is_capture(mv)) or (tBoard.is_en_passant(mv)):
					ttBoard = tBoard.copy()
					ttBoard.push(mv)
					if ttBoard.piece_at(tile) is None or ttBoard.piece_at(tile).color != self.color:
						#if ttBoard.status() == chess.STATUS_VALID or ttBoard.status() == chess.STATUS_OPPOSITE_CHECK:
						newBoards[ttBoard.fen()] = ttBoard.copy()
			#newBoards[k] = tBoard
		return newBoards

	def senseResultInference(self, sense_result, brds):
		newBoards = {}
		for k in brds:
			tBoard = brds[k].copy()
			good = True
			for square, piece in sense_result:
				if tBoard.piece_at(square) is None and piece is not None:
					good = False
					break
				elif tBoard.piece_at(square) is not None and piece is None:
					good = False
					break
				elif tBoard.piece_at(square) is not None and piece is not None:
					if tBoard.piece_at(square).piece_type != piece.piece_type:
						good = False
						break
					if tBoard.piece_at(square).color != piece.color:
						good = False
						break
			if good:
				newBoards[k] = brds[k].copy()
		return newBoards

	def moveResultInference(self, requested_move, taken_move, captured_opponent_piece, capture_square, brds):
		newBoards = {}
		for k in brds:
			tBoard = brds[k].copy()
			if tBoard.turn != self.color:
				tBoard.turn = self.color
				#print("null4")
			if taken_move is not None:
				if taken_move in tBoard.pseudo_legal_moves:
					if (captured_opponent_piece == True) and (tBoard.piece_at(capture_square) is not None) and (tBoard.piece_at(capture_square).piece_type != chess.KING):
						tBoard.push(taken_move)
						newBoards[tBoard.fen()] = tBoard.copy()
					elif (captured_opponent_piece == False) and (tBoard.piece_at(taken_move.to_square) is None):
						tBoard.push(taken_move)
						newBoards[tBoard.fen()] = tBoard.copy()
			elif requested_move is not None:
				if (tBoard.piece_at(requested_move.from_square) is not None) and (tBoard.piece_at(requested_move.from_square).piece_type == chess.PAWN):
					if tBoard.piece_at(requested_move.to_square) is None and (chess.square_file(requested_move.from_square) != chess.square_file(requested_move.to_square)):
						newBoards[k] = brds[k].copy()
					elif (chess.square_file(requested_move.from_square) == chess.square_file(requested_move.to_square)):
						if abs(chess.square_rank(requested_move.from_square) - chess.square_rank(requested_move.to_square)) == 2:
							if tBoard.piece_at(chess.square(chess.square_file(requested_move.to_square), (chess.square_rank(requested_move.from_square) + (1 if chess.square_rank(requested_move.to_square) > chess.square_rank(requested_move.from_square) else -1)))) is not None:
								newBoards[k] = brds[k].copy()
						else:
							if tBoard.piece_at(requested_move.to_square) is not None:
								newBoards[k] = brds[k].copy()
			else:
				newBoards[k] = brds[k].copy()
		return newBoards

	def recover(self):
		if len(self.potBoards) != 0:
			return None

		print("Recovering")
		reachedMove = self.moveNum + 1
		while len(self.checkpoints) != 0:
			(cN, brds) = self.checkpoints.pop(0)
			if cN < reachedMove:
				reachedMove = cN
			if len(brds) > 500:
					newBoards = {}
					for i in range(250):
						k = random.choice(list(brds))
						newBoards[k] = brds[k]
						brds.pop(k)
					self.checkpoints.add((cN, brds))
					brds = newBoards

			while (cN) < (len(self.opponent_move_results)):
				print(cN)
				if cN != -1:
					if cN < (len(self.sense_results)):
						brds = self.senseResultInference(self.sense_results[cN], brds)

					if len(brds) == 0:
						break

					if cN < (len(self.my_move_results)):
						(requested_move, taken_move, captured_opponent_piece, capture_square) = self.my_move_results[cN]
						brds = self.moveResultInference(requested_move, taken_move, captured_opponent_piece, capture_square, brds)
				cN = cN + 1

				if cN < (len(self.opponent_move_results)) and (cN > 0 or self.color == chess.BLACK):
					(cap, sqr) = self.opponent_move_results[cN]
					if cap:
						brds = self.advanceBoardsTaken(sqr, brds)
					else:
						brds = self.advanceBoardsNoTake(brds)

				if len(brds) > 500:
					newBoards = {}
					for i in range(250):
						k = random.choice(list(brds))
						newBoards[k] = brds[k]
						brds.pop(k)
					self.checkpoints.add((cN, brds))
					brds = newBoards

				if len(brds) == 0:
					break

			if len(brds) != 0:
				print("Recovered, earliest checkpoint reached - ", reachedMove)
				self.potBoards = brds
				return None
		print("!!!!!!! --- Failed to recover")

		return 1

	def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
		self.enemy = opponent_name
		self.color = color
		self.potBoards[board.fen()] = board.copy()
		tempD = {}
		tempD[board.fen()] = board
		self.checkpoints.add((-1, tempD))

	def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[Square]):
		self.mvRecovery = 0
		self.won = False
		print("")
		self.opponent_move_results.append((captured_my_piece, capture_square))
		if self.moveNum != 0 or self.color == chess.BLACK:
			if captured_my_piece:
				print("Piece taken at ", chess.SQUARE_NAMES[capture_square])
				self.potBoards = self.advanceBoardsTaken(capture_square, self.potBoards)
			else:
				self.potBoards = self.advanceBoardsNoTake(self.potBoards)
		self.recover()
		if len(self.potBoards) > 500:
			print("Checkpointing | len(potBoards) = ", len(self.potBoards), " | Num Checkpoints: ", len(self.checkpoints) + 1)
			newBoards = {}
			for b in self.potBoards:
				tBoard = self.potBoards[b].copy()
				king_square = tBoard.king(self.color)
				attackers = tBoard.attackers(not self.color, king_square)
				if len(attackers) != 0:
					newBoards[b] = self.potBoards[b]
			if len(list(newBoards)) != 0:
				print("\tChecked boards: ", len(list(newBoards)))
				for b in newBoards:
					self.potBoards.pop(b)
			for i in range((100 - len(list(newBoards)) if len(list(newBoards)) < 100 else 10)):
				if len(self.potBoards) == 0:
					break
				k = random.choice(list(self.potBoards))
				newBoards[k] = self.potBoards[k]
				self.potBoards.pop(k)
			self.checkpoints.add((self.moveNum, self.potBoards))
			self.potBoards = newBoards

	def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> \
			Optional[Square]:
		bDif = {}
		sqset = chess.SquareSet(chess.BB_ALL)
		for square in sqset:
			bDif[square] = (0, 0, 0, 0, 0, 0, 0)
		for k in self.potBoards:
			tBoard = self.potBoards[k].copy()
			for square in sqset:
				p = tBoard.piece_at(square)
				(n, pawn, knight, bishop, rook, queen, king) = bDif[square]
				if p is None:
					n = n + 1
				elif p.piece_type == chess.PAWN:
					pawn = pawn + 1
				elif p.piece_type == chess.KNIGHT:
					knight = knight + 1
				elif p.piece_type == chess.BISHOP:
					bishop = bishop + 1
				elif p.piece_type == chess.ROOK:
					rook = rook + 1
				elif p.piece_type == chess.QUEEN:
					queen = queen + 1
				elif p.piece_type == chess.KING:
					king = king + 1

				bDif[square] = (n, pawn, knight, bishop, rook, queen, king)
		minSq = None
		minNum = 0
		for i in range(6):
			for j in range(6):
				ct = 0
				sq = chess.square(i+1, j+1)
				for k in range(3):
					for l in range(3):
						siph = chess.square(i+k, j+l)
						ct = ct + len(self.potBoards) - max(bDif[siph])
				if ct > minNum:
					minNum = ct
					minSq = sq

		if minSq is None and (len(self.checkpoints) == 0 or self.checkpoints[-1][0] == -1):
			print("No scan needed")
			return None
		elif minSq is None and (len(self.checkpoints) != 0 and self.checkpoints[-1][0] != -1):
			print("Somewhat sure of board state, random sense")
			for k in self.potBoards:
				for square, piece in self.potBoards[k].piece_map().items():
					if square in sense_actions:
						if piece.color == self.color:
							sense_actions.remove(square)
			return random.choice(sense_actions)
		else:
			return minSq

	def handle_sense_result(self, sense_result: List[Tuple[Square, Optional[chess.Piece]]]):
		self.sense_results.append(sense_result)
		self.potBoards = self.senseResultInference(sense_result, self.potBoards)
		self.recover()

	def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
		if self.mvRecovery > 3:
			return None

		self.approxTime = seconds_left
		score = 0
		count = 0
		lowestMove = None
		lowScore = float("inf")
		timelimit = 0.0
		moves = SortedList(key=lambda x: x[1])
		checks = SortedList(key=lambda x: x[1])
		mates = []

		if len(self.potBoards) != 0:
			timelimit = 2.0 / len(self.potBoards)
		else:
			timelimit = 1.0

		for k in self.potBoards:
			tBoard = chess.Board(k)

			enemy_king_square = tBoard.king(not self.color)
			if enemy_king_square:
				# if there are any ally pieces that can take king, execute one of those moves
				enemy_king_attackers = tBoard.attackers(self.color, enemy_king_square)
				while enemy_king_attackers is not None and len(enemy_king_attackers) != 0:
					attacker_square = enemy_king_attackers.pop()
					mv = chess.Move(attacker_square, enemy_king_square)
					if mv in move_actions:
						mates.append(mv)
						score = score + 100000
						count = count + 1
						continue

			if tBoard.turn != self.color:
				tBoard.turn = not self.color
				#print("null3")
			king_square = tBoard.king(self.color)
			attackers = tBoard.attackers(not self.color, king_square)
			tBoard.clear_stack()

			if tBoard.status() == chess.STATUS_VALID:
				try:
					result = self.engine.play(tBoard, chess.engine.Limit(time=timelimit), root_moves = move_actions)
					if result is not None and result.move is not None:
						tBoard.push(result.move)
						tBoard.clear_stack()
						info = self.engine.analyse(tBoard, chess.engine.Limit(time=timelimit/10.0))
						score = score + info["score"].pov(self.color).score(mate_score=100000)
						if len(attackers) != 0:
							checks.add((result.move, info["score"].pov(self.color).score(mate_score=100000)))
						else:
							moves.add((result.move, info["score"].pov(self.color).score(mate_score=100000)))
						count = count + 1
				except (chess.engine.EngineError, chess.engine.EngineTerminatedError) as e:
					print('2!!!!!!!!!!! -- Engine bad state at "{}"'.format(tBoard.fen()))
					self.engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
			

		if count != 0:
			self.score = score / count
		else:
			print("No valid moves found")
			if (len(self.checkpoints) != 0) and (self.checkpoints[-1][0] != 0):
				print("\tRefreshing state stack")
				toAdd = {}
				for b in self.potBoards:
					toAdd[b] = self.potBoards[b]
				for b in toAdd:
					self.potBoards.pop(b)
				self.recover()
				self.checkpoints.add((self.moveNum, toAdd))
				self.recover()
				print("\tChoosing new move")
				self.mvRecovery = self.mvRecovery + 1
				return self.choose_move(move_actions, seconds_left)

		firstChoice = None
		mateChoice = False
		while len(mates) != 0:
			mv = mates.pop(0)
			if firstChoice is None:
				firstChoice = mv
				mateChoice = True
			good = True
			for b in self.potBoards:
				tBoard = chess.Board(b)
				if mv in tBoard.pseudo_legal_moves:
					if tBoard.is_into_check(mv):
						good = False
						break
				else:
					if tBoard.is_check():
						good = False
						break
			if good:
				print("Mate!!! ", mv)
				self.won = True
				return mv

		while len(checks) != 0:
			(mv, s) = checks.pop(0)

			if mv in move_actions:
				if firstChoice is None:
					firstChoice = mv

				good = True
				for b in self.potBoards:
					tBoard = chess.Board(b)
					if mv in tBoard.pseudo_legal_moves:
						if tBoard.is_into_check(mv):
							good = False
							break
					else:
						if tBoard.is_check():
							good = False
							break
				if good:
					print("Checked?! ", mv)
					return mv

		while len(moves) != 0:
			(mv, s) = moves.pop(0)

			if mv in move_actions:
				if firstChoice is None:
					firstChoice = mv

				good = True
				for b in self.potBoards:
					tBoard = chess.Board(b)
					if mv in tBoard.pseudo_legal_moves:
						if tBoard.is_into_check(mv):
							good = False
							break
					else:
						if tBoard.is_check():
							good = False
							break
				if good:
					print(mv)
					return mv

		for mv in move_actions:
			good = True
			for b in self.potBoards:
				tBoard = chess.Board(b)
				if mv in tBoard.pseudo_legal_moves:
					if tBoard.is_into_check(mv):
						good = False
						break
				else:
					if tBoard.is_check():
						good = False
						break
			if good:
				print("Safe Move? ", mv)
				return mv

		if firstChoice is not None:
			print("May be moving into check")
			print(firstChoice)
			self.won = mateChoice
			return firstChoice

		print("No valid move chosen")
		return None

	def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
						   captured_opponent_piece: bool, capture_square: Optional[Square]):
		self.my_move_results.append((requested_move, taken_move, captured_opponent_piece, capture_square))
		if captured_opponent_piece:
			print("I killed something")
		newBoards = {}
		self.potBoards = self.moveResultInference(requested_move, taken_move, captured_opponent_piece, capture_square, self.potBoards)
		if not self.won:
			self.recover()

		#if taken_move is not None:
		#	self.board.push(taken_move)
		self.moveNum = self.moveNum + 1

		print("Considering ", len(self.potBoards), " potential board states || Earliest Checkpoint: ", self.checkpoints[0][0] if len(self.checkpoints) != 0 else "---")
		print ("StockyInf.:\t End move ", self.moveNum, " -- approx ", '{:06.2f}'.format(self.approxTime), " seconds left || Score: ", '{:06.1f}'.format(self.score))

	def handle_game_end(self, winner_color: Optional[Color], win_reason: Optional[WinReason],
						game_history: GameHistory):
		
		winner = ""
		white_bot_name = ""
		black_bot_name = ""
		timestamp = ""

		if self.color == chess.WHITE:
			white_bot_name = "StockyInference"
			black_bot_name = self.enemy
		else:
			black_bot_name = "StockyInference"
			white_bot_name = self.enemy

		if winner_color == chess.WHITE:
			winner = "WHITE"
		else:
			winner = "BLACK"

		timestamp = datetime.datetime.now().strftime('%Y_%m_%d-%H_%M_%S')
		replay_path = '{}-{}-{}-{}.json'.format(white_bot_name, black_bot_name, winner, timestamp)
		#game_history.save(replay_path)
		try:
			self.engine.quit()
		except:
			print("Engine quit failed")
