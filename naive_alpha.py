import random
from reconchess import *
from sortedcontainers import SortedList

#change from DefensiveScan: Only adds win or loss condition if it reaches check on right turn
class NaiveAlpha(Player):
	def __init__(self):
		self.board = None
		self.color = None
		self.moveNum = 0
		self.nextMove = None
		self.expectedEnemy = None
		self.approxTime = 900
		self.interestingTile = None
		self.expectedScore = 0
		self.panic = False
		self.score = 0
		self.lastScanned = {}
		self.observedMoves = 0

	def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
		self.board = board
		self.color = color

		allSqr = chess.SquareSet(chess.BB_ALL)
		for square in allSqr:
			self.lastScanned[square] = 0

	def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[Square]):
		if captured_my_piece:
			self.interestingTile = capture_square
			self.board.remove_piece_at(capture_square)

	def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> \
			Optional[Square]:

		allSqr = chess.SquareSet(chess.BB_ALL)
		for square in allSqr:
			if self.board.piece_at(square) is not None and self.board.piece_at(square).color == self.color:
				self.lastScanned[square] = 0
			else:
				self.lastScanned[square] = self.lastScanned[square] + 1

		self.moveNum = self.moveNum + 1
		if self.panic:
			for square, piece in self.board.piece_map().items():
				if piece.color == self.color:
					sense_actions.remove(square)
			return random.choice(sense_actions)

		if self.interestingTile:
			print("Scanning interesting tile")
			return self.interestingTile

		if self.expectedEnemy is not None:
			if self.board.piece_at(self.expectedEnemy.to_square) is None:
				print("Scanning expected move")
				return self.expectedEnemy.to_square

		m_king_square = self.board.king(self.color)
		if m_king_square:
			attackers = self.board.attackers(not self.color, m_king_square)
			if not attackers:
				potentialThreats = SortedList(key=lambda x: x[1])
				tB = self.board.copy()
				bfs = []
				bfs.append((tB, None, 0, -1))

				while len(bfs) > 0:
					cS = bfs.pop(0)
					if cS[0].turn == self.color:
						cS[0].push(chess.Move.null())
					m_king_square = cS[0].king(self.color)
					if m_king_square:
						attackers = cS[0].attackers(not self.color, m_king_square)
						if attackers:
							potentialThreats.add((cS[1], self.lastScanned[cS[1]]))
							continue
					for mv in cS[0].legal_moves:
						if cS[2] >= 3:
							continue
						if cS[2] >= cS[3] and cS[3] != -1:
							continue
						if cS[0].piece_at(mv.to_square) is not None:
							continue
						if self.lastScanned[mv.from_square] <= 1:
							continue
						nB = cS[0].copy()
						nB.push(mv)
						if cS[3] != -1:
							bfs.append((nB, cS[1] if cS[1] is not None else mv.to_square, cS[2] + 1, min(cS[3], cS[2] + self.lastScanned[mv.to_square])))
						else:
							bfs.append((nB, cS[1] if cS[1] is not None else mv.to_square, cS[2] + 1, self.lastScanned[mv.from_square]))

				if len(potentialThreats) > 0:
					pot = potentialThreats.pop(-1)
					print("Scanning threat: ", chess.SQUARE_NAMES[pot[0]])
					return pot[0]

		self.nextMove = self.choose_move(move_actions, seconds_left)
		if self.nextMove is not None:
			print("Scanning next move")
			return self.nextMove.to_square

		for square, piece in self.board.piece_map().items():
			if piece.color == self.color:
				sense_actions.remove(square)

		print("Scanning random")
		return random.choice(sense_actions)

	def handle_sense_result(self, sense_result: List[Tuple[Square, Optional[chess.Piece]]]):
		self.interestingTile = None
		for square, piece in sense_result:
			self.lastScanned[square] = 0
			if self.board.piece_at(square) != piece:
				self.nextMove = None
				if self.board.piece_at(square) is None:
					if self.board.turn is self.color:
						self.board.push(chess.Move.null())
					for move in self.board.legal_moves:
						if move.to_square == square and self.board.piece_at(move.from_square) == piece:
							self.board.push(move)
							break


		#	if self.expectedEnemy is not None and piece is not None and self.board.piece_at(self.expectedEnemy.from_square) is not None:
		#		if self.expectedEnemy.to_square == square and self.board.piece_at(self.expectedEnemy.from_square).piece_type == piece.piece_type:
		#			self.board.push(self.expectedEnemy)

			if piece is None:
				self.board.remove_piece_at(square)
			else:
				self.board.set_piece_at(square, piece)

	def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
		self.approxTime = seconds_left
		self.response = None
		if self.nextMove is not None:
			mv = self.nextMove
			self.nextMove = None
			return mv

		if self.board.turn is not self.color:
			self.board.push(chess.Move.null())

		e_king_square = self.board.king(not self.color)
		if e_king_square:
			attackers = self.board.attackers(self.color, e_king_square)
			for attack in attackers:
				m = chess.Move(attack, e_king_square)
				if m in move_actions:
					return m

	#	m_king_square = self.board.king(self.color)
	#	if m_king_square:
	#		attackers = self.board.attackers(not self.color, m_king_square)
	#		if attackers:
	#			legalMoves = self.board.legal_moves
	#			for move in legalMoves:
	#				tempBoard = self.board.copy()
	#				tempBoard.push(move)
	#				attackers = tempBoard.attackers(not self.color, tempBoard.king(self.color))
	#				if (attackers is None or len(attackers) is 0) and move in move_actions:
	#					return move

		class State:
			def __init__(self, board, iM):
				self.brd = board
				self.score = 0
				self.initialMove = iM
				self.responses = SortedList(key=lambda x: x.score)

		def eval_board(board) -> float:
			score = 0
			for square, piece in board.piece_map().items():
				mult = 1
				val = 0
				if piece.color != self.color:
					mult = -1
				if piece.piece_type == chess.PAWN:
					val = 1
				elif piece.piece_type == chess.KNIGHT:
					val = 10
				elif piece.piece_type == chess.BISHOP:
					val = 10
				elif piece.piece_type == chess.ROOK:
					val = 10
				elif piece.piece_type == chess.QUEEN:
					val = 20
				elif piece.piece_type == chess.KING:
					val = 1000
				attackers = board.attackers(not piece.color, square)
				#defenders = self.board.attackers(piece.color, square)
				if piece.piece_type == chess.KING and len(attackers) != 0:
					score = score - mult * 500

				#if len(attackers) != 0 and len(defenders) == 0 and piece.color == self.color:
				#	val = val / 10
				#if len(defenders) != 0 and piece.piece_type != chess.KING and piece.color != self.color:
				#	val = val * 2

				score = score + mult * val
			return score
		self.score = eval_board(self.board)

		wasKing = False
		if self.board.king(not self.color):
			wasKing = True
		else:
			wasKing = False
			self.panic = True
		
		def alphabeta(board, depth, alpha, beta, maximizing) -> float:
			terminal = False
			mod = 0
			if wasKing:
				e_king_square = board.king(not self.color)
				if not e_king_square:
					terminal = True
					mod = 1000
				elif maximizing:
					attackers = board.attackers(self.color, e_king_square)
					if attackers:
						mod = 1000
						terminal = True
			m_king_square = board.king(self.color)
			if not m_king_square:
				terminal = True
				mod = -1000
			elif not maximizing:
				attackers = board.attackers(not self.color, m_king_square)
				if attackers:
					mod = -1000
					terminal = True
			if depth == 0 or terminal:
				return (eval_board(board) + mod, None, None)

			if maximizing:
				if board.turn != self.color:
					board.push(chess.Move.null())
				val = float("-inf")
				bM = []
				for mv in board.pseudo_legal_moves:
					tB = board.copy()
					tB.push(mv)
					(v, m, r) = alphabeta(tB, depth - 1, alpha, beta, False)

					if v > val:
						bM = [(mv, m)]
						val = v
					elif v == val:
						bM.append((mv,m))

					alpha = max(alpha, val)
					if alpha >= beta:
						break
				if len(bM) == 0:
					return (val, None, None)
				else:
					(mov, resp) = random.choice(bM)
					return (val, mov, resp)
			else:
				if board.turn == self.color:
					board.push(chess.Move.null())
				val = float("inf")
				bM = []
				res = []
				for mv in board.pseudo_legal_moves:
					tB = board.copy()
					tB.push(mv)
					(v, m, r) = alphabeta(tB, depth - 1, alpha, beta, True)

					if v < val:
						bM = [(mv, m)]
						val = v
					elif v == val:
						bM.append((mv,m))

					beta = min(beta, val)
					if alpha >= beta:
						break
				if len(bM) == 0:
					return (val, None, None)
				else:
					(mov, resp) = random.choice(bM)
					return (val, mov, resp)

		(v, m, e) = alphabeta(self.board, 4, float("-inf"), float("inf"), True)
		self.expectedScore = v
		self.expectedEnemy = e
		if m in move_actions:
			print(m)
			return m
		else:
			print("Illegal move requested")
			print(m)
			return None

		#return random.choice(move_actions + [None])

	def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
						   captured_opponent_piece: bool, capture_square: Optional[Square]):
		if taken_move is not None:
			self.board.push(taken_move)
			if requested_move is not taken_move:
				self.interestingTile = taken_move.to_square
		else:
			if requested_move is not taken_move:
				self.interestingTile = requested_move.to_square

		print ("NaiveAlpha:\t End move ", self.moveNum, " -- approx ", '{:06.2f}'.format(self.approxTime), " seconds left || Score: ", '{:06.1f}'.format(self.score), "Expected Score: ", '{:06.1f}'.format(self.expectedScore))
		if self.panic:
			print("\tWe lost track of their king.")

	def handle_game_end(self, winner_color: Optional[Color], win_reason: Optional[WinReason],
						game_history: GameHistory):
		pass
